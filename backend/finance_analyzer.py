from parse_management_fee import parse_management_fee_sheet
from clean_bank_tx import process_bank_transactions
import re
from sqlalchemy.orm import Session
from sqlalchemy import func
import models

def normalize_code(code):
    """Normalize code to compare C06 vs C6 etc."""
    code = code.upper()
    # Remove leading zeros from digits
    return re.sub(r'0+(\d+)', r'\1', code)

def recalculate_arrears_forward(db: Session, unit_id: int):
    """
    Recalculates previous_arrears for all future billing months for a given unit.
    Should be called after any modification to a billing's paid amount or expected fees.
    """
    billings = db.query(models.MonthlyBilling).filter(
        models.MonthlyBilling.unit_id == unit_id
    ).order_by(models.MonthlyBilling.billing_month).all()

    running_arrears = 0
    for b in billings:
        b.previous_arrears = running_arrears
        # Expected amount is the fees for this month PLUS the arrears (which could be negative if overpaid)
        expected_amount = b.total_expected + b.previous_arrears
        
        # Direct query to avoid SQLAlchemy relationship cache issues on the same session
        actual_paid_result = db.query(func.sum(models.PaymentReconciliation.allocated_amount))\
            .filter(models.PaymentReconciliation.monthly_billing_id == b.id)\
            .scalar()
        actual_paid = actual_paid_result if actual_paid_result else 0
        
        # Calculate what rolls over to the next month
        # If they underpaid, running_arrears goes up (positive).
        # If they overpaid, running_arrears goes down (negative).
        running_arrears = expected_amount - actual_paid
        
        # Also fix the status while we're sweeping forward
        if actual_paid > expected_amount:
            b.status = "Overpaid"
        elif actual_paid == expected_amount and expected_amount > 0:
            b.status = "Paid"
        elif actual_paid == 0:
            b.status = "Unpaid"
        else:
            b.status = "Underpaid"

    db.commit()

def reconcile_finances(db: Session, bank_path, virtual_path, billing_month="2026-01"):
    transactions = process_bank_transactions(bank_path, virtual_path)
    
    actual_payments_by_code = {}
    for tx in transactions:
        code = tx.get('code', '')
        
        # Parse amounts from formatted strings
        income_str = str(tx.get('income', '')).replace(',', '').replace('.0', '').strip()
        expense_str = str(tx.get('expense', '')).replace(',', '').replace('.0', '').strip()
        amount = 0
        if income_str and income_str.isdigit():
            amount = int(income_str)
        elif expense_str and expense_str.isdigit():
            amount = -int(expense_str)
        
        # Save ALL transactions to DB so they can be retrieved later
        db_tx = models.BankTransaction(
            tx_date=str(tx.get('date', '')),
            amount=amount,
            transaction_code=code,
            billing_month=billing_month,
            category=str(tx.get('category', '')),
            virtual_account=str(tx.get('virtualAccount', '')),
            balance=str(tx.get('balance', '')),
            details=str(tx.get('remarks', ''))
        )
        db.add(db_tx)
        db.flush()

        # Only track income transactions for reconciliation matching
        if amount > 0 and code:
            if code not in actual_payments_by_code:
                actual_payments_by_code[code] = []
            actual_payments_by_code[code].append({"amount": amount, "db_tx_id": db_tx.id})

    # Fetch expected households from DB
    billings = db.query(models.MonthlyBilling).filter(models.MonthlyBilling.billing_month == billing_month).all()

    orphaned_payments = []

    for b in billings:
        u = b.unit
        expected_amount = b.total_expected + b.previous_arrears
        
        actual_paid = 0
        matched_keys = []
        
        clean_unit = u.virtual_account_code if u.virtual_account_code else u.unit_code.split('(')[0]
        norm_unit = normalize_code(clean_unit)
        
        for code, payments in actual_payments_by_code.items():
            norm_code = normalize_code(code)
            
            # Use regex boundary \b to prevent partial matches like 'C1' matching 'C11'
            if norm_code == norm_unit or re.search(r'\b' + re.escape(norm_unit) + r'\b', norm_code):
                for p in payments:
                    alloc_amount = p["amount"]
                    actual_paid += alloc_amount
                    
                    # Create reconciliation record
                    rec = models.PaymentReconciliation(
                        bank_transaction_id=p["db_tx_id"],
                        monthly_billing_id=b.id,
                        allocated_amount=alloc_amount
                    )
                    db.add(rec)
                    
                    # Update matched_unit_id on bank_transaction
                    db_tx = db.query(models.BankTransaction).filter_by(id=p["db_tx_id"]).first()
                    if db_tx:
                         db_tx.matched_unit_id = u.id
                    
                matched_keys.append(code)

        for k in matched_keys:
            if k in actual_payments_by_code:
                del actual_payments_by_code[k]

        # Update billing status taking arrears into account
        # Status is now primarily handled by the forward scanner
        # Let's just calculate it for immediate feedback 
        if actual_paid > expected_amount:
            b.status = "Overpaid"
        elif actual_paid == expected_amount and expected_amount > 0:
            b.status = "Paid"
        elif actual_paid == 0:
            b.status = "Unpaid"
        else:
            b.status = "Underpaid"

    db.commit()
    
    # After pushing all new payments, recalculate arrears forward for all units
    distinct_unit_ids = {b.unit_id for b in billings}
    for uid in distinct_unit_ids:
        recalculate_arrears_forward(db, uid)

    # orphaned payments
    for code, payments in actual_payments_by_code.items():
        for p in payments:
            orphaned_payments.append({
                "code": code,
                "amount": p["amount"]
            })

    db.commit()

    # Re-fetch formatted households using our existing function to power frontend
    updated_records = get_db_households(db, billing_month)
    return {
        "transactions": transactions,
        "reconciliation": {
            "paid": [r for r in updated_records if r["status"] in ("Paid", "Overpaid")],
            "unpaid": [r for r in updated_records if r["status"] not in ("Paid", "Overpaid")],
            "orphaned": orphaned_payments
        }
    }

def get_db_households(db: Session, billing_month: str = "2026-01"):
    billings = db.query(models.MonthlyBilling).filter(models.MonthlyBilling.billing_month == billing_month).all()
    
    records = []
    # Sort billings roughly by ID to maintain the seeded order
    billings = sorted(billings, key=lambda b: b.id)
    
    for idx, b in enumerate(billings):
        u = b.unit
        resident = next((r for r in u.residents if r.role == 'Owner'), next((r for r in u.residents), None))
        name = resident.name if resident else ""
        
        car_parks = "、".join([p.asset_number for p in u.parking_assets if p.type == 'Car'])
        scooter_parks = "、".join([p.asset_number for p in u.parking_assets if p.type == 'Scooter'])
        bike_parks = "、".join([p.asset_number for p in u.parking_assets if p.type == 'Bike'])
        
        # compute paid amount
        paid_amount = sum([r.allocated_amount for r in b.reconciliations]) if b.reconciliations else 0
        
        # Expected is strictly the current month's fees, not including arrears.
        current_expected_amount = b.total_expected 
        
        # Total due for status evaluation includes arrears
        total_due = b.total_expected + b.previous_arrears
        
        # Re-evaluate status just in case
        status = b.status
        if paid_amount == 0 and total_due > 0:
            status = "Unpaid"
        
        records.append({
            "id": b.id,
            "unit": u.unit_code,
            "order": idx,
            "address": u.address,
            "floor": u.floor,
            "virtual_account_code": u.virtual_account_code,
            "name": name,
            "car_parking": car_parks,
            "scooter_parking": scooter_parks,
            "bike_parking": bike_parks,
            "base_fee": b.base_fee,
            "car_cleaning_fee": b.car_cleaning_fee,
            "scooter_cleaning_fee": b.scooter_cleaning_fee,
            "bike_cleaning_fee": b.bike_cleaning_fee,
            "temp_rent": b.temp_rent,
            "previous_arrears": b.previous_arrears,
            "expected": current_expected_amount,
            "paid": paid_amount,
            "status": status,
            "unit_clean": u.virtual_account_code
        })
        
    return records
