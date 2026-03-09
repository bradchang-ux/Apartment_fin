from database import SessionLocal, engine, Base
from models import Unit, Resident, ParkingAsset, MonthlyBilling
from parse_management_fee import parse_management_fee_sheet
import os
import json

def seed_database(force=False):
    # 1. Create tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # 2. Check if already seeded
    existing = db.query(Unit).count()
    if existing > 0 and not force:
        print(f"Database already contains {existing} units. Skipping seed.")
        db.close()
        return

    # 3. Parse data - try Excel first, fallback to JSON
    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '11501月財報資料.xlsx'))
    json_path = os.path.join(os.path.dirname(__file__), 'seed_data.json')
    
    households = None
    if os.path.exists(report_path):
        print(f"Parsing Excel: {report_path}...")
        try:
            households = parse_management_fee_sheet(report_path)
        except Exception as e:
            print(f"Failed to parse excel: {e}")
    
    if not households and os.path.exists(json_path):
        print(f"Loading seed data from JSON: {json_path}...")
        with open(json_path, 'r', encoding='utf-8') as f:
            households = json.load(f)
    
    if not households:
        print("No seed data available (neither Excel nor JSON found).")
        db.close()
        return
        
    print(f"Found {len(households)} households to seed.")

    # 4. Insert data
    # Create multiple billing periods
    
    for details in households:
        # Extract base strings
        unit_str = details['unit']
        floor_str = details['floor']
        name_str = details['name']
        address_str = f"{floor_str}樓 {unit_str}"
        
        clean_unit = unit_str.split('(')[0]
        virtual_code = clean_unit # Rough approximation, we know C6 is C06 in reality, we handle that in logic
        
        # Create or Get Unit
        db_unit = db.query(Unit).filter_by(unit_code=unit_str).first()
        if not db_unit:
            db_unit = Unit(
                unit_code=unit_str,
                address=address_str,
                floor=floor_str,
                virtual_account_code=virtual_code
            )
            db.add(db_unit)
            db.flush() # flush to get db_unit.id
        
        # Create Resident
        if name_str:
            db_resident = Resident(
                unit_id=db_unit.id,
                name=name_str,
                role="Owner" # Defaulting for now
            )
            db.add(db_resident)

        # Create Parking Assets
        if details.get('car_parking'):
            for p in details['car_parking'].split('、'):
               if p.strip():
                   db.add(ParkingAsset(unit_id=db_unit.id, type="Car", asset_number=p.strip(), cleaning_fee=details.get('car_cleaning_fee', 0)))
        
        if details.get('scooter_parking'):
            for p in details['scooter_parking'].split('、'):
               if p.strip():
                   db.add(ParkingAsset(unit_id=db_unit.id, type="Scooter", asset_number=p.strip(), cleaning_fee=details.get('scooter_cleaning_fee', 0)))

        if details.get('bike_parking'):
            for p in details['bike_parking'].split('、'):
               if p.strip():
                   db.add(ParkingAsset(unit_id=db_unit.id, type="Bike", asset_number=p.strip(), cleaning_fee=details.get('bike_cleaning_fee', 0)))
                   
        # Calculate fallback expected if excel parsing returns 0
        expected_raw = details.get('expected', 0)
        if expected_raw == 0:
             expected_raw = (
                 details.get('base_fee', 0) +
                 details.get('car_cleaning_fee', 0) +
                 details.get('scooter_cleaning_fee', 0) +
                 details.get('bike_cleaning_fee', 0) +
                 details.get('temp_rent', 0)
             )
                   
        # Create Monthly Billing for multiple periods
        running_arrears = 0
        for month_str in ["2026-01", "2026-02", "2026-03"]:
            db_billing = MonthlyBilling(
                unit_id=db_unit.id,
                billing_month=month_str,
                base_fee=details.get('base_fee', 0),
                car_cleaning_fee=details.get('car_cleaning_fee', 0),
                scooter_cleaning_fee=details.get('scooter_cleaning_fee', 0),
                bike_cleaning_fee=details.get('bike_cleaning_fee', 0),
                temp_rent=details.get('temp_rent', 0),
                previous_arrears=running_arrears,
                total_expected=expected_raw,
                status="Unpaid"
            )
            db.add(db_billing)
            
            # Since no payment is made during seeding, the amount expected becomes next month's arrears
            running_arrears += expected_raw

    print("Committing to database...")
    db.commit()
    db.close()
    print("Database seeding complete!")

if __name__ == "__main__":
    seed_database()
