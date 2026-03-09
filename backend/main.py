from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
from pathlib import Path
import datetime
from database import SessionLocal, engine, Base
import models
import schemas
import shutil
from clean_bank_tx import process_bank_transactions
from finance_analyzer import reconcile_finances, get_db_households, recalculate_arrears_forward
from seed_db import seed_database

# Ensure tables are created and seed data exists
models.Base.metadata.create_all(bind=engine)
try:
    seed_database()  # Auto-seed on startup (skips if already seeded)
except Exception as e:
    import traceback
    print(f"Seed failed on startup: {e}")
    traceback.print_exc()

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Allow CORS for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/api/upload")
async def upload_files(
    billing_month: str = Form(...),
    bank_file: UploadFile = File(...),
    virtual_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        bank_path = os.path.join(UPLOAD_DIR, bank_file.filename)
        with open(bank_path, "wb") as buffer:
            shutil.copyfileobj(bank_file.file, buffer)
            
        virtual_path = None
        if virtual_file:
            virtual_path = os.path.join(UPLOAD_DIR, virtual_file.filename)
            with open(virtual_path, "wb") as buffer:
                shutil.copyfileobj(virtual_file.file, buffer)

        # Process the files with full database reconciliation targeted at the specified month
        results = reconcile_finances(db, bank_path, virtual_path, billing_month=billing_month)
        
        return {
            "message": f"Files processed and reconciled successfully for {billing_month}",
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/households")
def get_households(month: str = None, db: Session = Depends(get_db)):
    try:
        # Determine available months from DB
        billing_months = db.query(models.MonthlyBilling.billing_month).distinct().all()
        available_months = sorted([m[0] for m in billing_months], reverse=True)
        
        # Default to the most recent month if none provided
        target_month = month
        if not target_month:
            target_month = available_months[0] if available_months else "2026-01"

        households = get_db_households(db, billing_month=target_month)
        
        return {
            "message": "Households loaded successfully",
            "meta": {
                "available_months": available_months,
                "selected_month": target_month
            },
            "data": households
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/transactions")
def get_transactions(month: str = None, db: Session = Depends(get_db)):
    try:
        query = db.query(models.BankTransaction)
        if month:
            query = query.filter(models.BankTransaction.billing_month == month)
        txs = query.order_by(models.BankTransaction.id).all()
        
        data = []
        for tx in txs:
            amount = tx.amount
            fmt_income = f"{amount:,}" if amount > 0 else ""
            fmt_expense = f"{abs(amount):,}" if amount < 0 else ""
            
            data.append({
                "date": tx.tx_date,
                "category": tx.category or "",
                "code": tx.transaction_code,
                "income": fmt_income,
                "expense": fmt_expense,
                "balance": tx.balance or "",
                "remarks": tx.details or "",
                "virtualAccount": tx.virtual_account or ""
            })
        
        return {"data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/households/{household_id}")
def update_household(household_id: int, update_data: schemas.HouseholdRecordUpdate, db: Session = Depends(get_db)):
    try:
        # `household_id` represents the MonthlyBilling ID in our schema representation
        billing = db.query(models.MonthlyBilling).filter(models.MonthlyBilling.id == household_id).first()
        if not billing:
            raise HTTPException(status_code=404, detail="Household / Billing record not found")
        
        # Update Billing numeric fields
        fees_updated = False
        if update_data.base_fee is not None: 
            billing.base_fee = update_data.base_fee
            fees_updated = True
        if update_data.car_cleaning_fee is not None: 
            billing.car_cleaning_fee = update_data.car_cleaning_fee
            fees_updated = True
        if update_data.scooter_cleaning_fee is not None: 
            billing.scooter_cleaning_fee = update_data.scooter_cleaning_fee
            fees_updated = True
        if update_data.bike_cleaning_fee is not None: 
            billing.bike_cleaning_fee = update_data.bike_cleaning_fee
            fees_updated = True
        if update_data.temp_rent is not None: 
            billing.temp_rent = update_data.temp_rent
            fees_updated = True
            
        if fees_updated:
            billing.total_expected = (billing.base_fee + billing.car_cleaning_fee + 
                                      billing.scooter_cleaning_fee + billing.bike_cleaning_fee + 
                                      billing.temp_rent)

        if update_data.paid is not None:
             current_paid = sum([r.allocated_amount for r in billing.reconciliations]) if billing.reconciliations else 0
             delta = update_data.paid - current_paid
             
             if delta != 0:
                 # Create a simulated BankTransaction to account for the manual adjustment
                 manual_tx = models.BankTransaction(
                     tx_date=datetime.datetime.now().strftime("%Y/%m/%d"),
                     amount=delta,
                     transaction_code="Manual Entry",
                     matched_unit_id=billing.unit_id,
                     details="Manual UI override"
                 )
                 db.add(manual_tx)
                 db.flush() # get the ID
                 
                 # Create the mapping
                 recon = models.PaymentReconciliation(
                     bank_transaction_id=manual_tx.id,
                     monthly_billing_id=billing.id,
                     allocated_amount=delta
                 )
                 db.add(recon)
                 db.flush()

        # Recalculate status unconditionally at the end to cover fee changes and paid changes
        if update_data.paid is not None:
            updated_paid = update_data.paid
        else:
            updated_paid = sum([r.allocated_amount for r in billing.reconciliations]) if billing.reconciliations else 0
            
        expected_amount = billing.total_expected + billing.previous_arrears
        if updated_paid > expected_amount:
            billing.status = "Overpaid"
        elif updated_paid == expected_amount and expected_amount > 0:
            billing.status = "Paid"
        elif updated_paid == 0:
            billing.status = "Unpaid"
        else:
            billing.status = "Underpaid"

        # Update Resident Name if provided
        if update_data.name is not None:
             u = billing.unit
             resident = next((r for r in u.residents if r.role == 'Owner'), next((r for r in u.residents), None))
             if resident:
                  resident.name = update_data.name
             else:
                  # Create new resident if none existed
                  new_res = models.Resident(unit_id=u.id, name=update_data.name, role="Owner")
                  db.add(new_res)
                  
        db.commit()
        
        # Recalculate arrears forward for this unit now that data was manually changed
        recalculate_arrears_forward(db, billing.unit_id)

        # Re-fetch the updated household record to return the new status
        updated_records = get_db_households(db, billing.billing_month)
        updated_billing = next((r for r in updated_records if r["id"] == household_id), None)
        
        return {"message": "Household updated successfully", "data": updated_billing}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/debug")
def debug_info(db: Session = Depends(get_db)):
    import os
    seed_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'seed_data.json')
    return {
        "cwd": os.getcwd(),
        "seed_json_path": seed_json,
        "seed_json_exists": os.path.exists(seed_json),
        "units_count": db.query(models.Unit).count(),
        "billings_count": db.query(models.MonthlyBilling).count(),
        "dir_contents": os.listdir(os.path.dirname(os.path.abspath(__file__)))
    }

@app.post("/api/reset_db")
def reset_db(db: Session = Depends(get_db)):
    try:
        db.close()  # Close the injected session first
        
        # Drop all tables and recreate to ensure schema is up to date
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        # Reseed the database with force=True to skip the "already seeded" check
        seed_database(force=True)
        
        return {"message": "Database reset and seeded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve frontend static files in production
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Try to serve the exact file first
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # Fallback to index.html for SPA routing
        return FileResponse(str(FRONTEND_DIR / "index.html"))
