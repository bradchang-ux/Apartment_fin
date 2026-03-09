from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Date, Boolean
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    unit_code = Column(String, unique=True, index=True, nullable=False) # e.g. A1, B2
    address = Column(String) # e.g. 215號
    floor = Column(String) # e.g. 1
    virtual_account_code = Column(String, index=True) # e.g. C6

    residents = relationship("Resident", back_populates="unit")
    parking_assets = relationship("ParkingAsset", back_populates="unit")
    monthly_billings = relationship("MonthlyBilling", back_populates="unit")

class Resident(Base):
    __tablename__ = "residents"

    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"))
    name = Column(String, nullable=False)
    role = Column(String) # Owner or Tenant
    move_in_date = Column(Date, nullable=True)
    move_out_date = Column(Date, nullable=True)

    unit = relationship("Unit", back_populates="residents")

class ParkingAsset(Base):
    __tablename__ = "parking_assets"

    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"))
    type = Column(String, nullable=False) # Car, Scooter, Bike
    asset_number = Column(String) # B2-45
    cleaning_fee = Column(Integer, default=0)

    unit = relationship("Unit", back_populates="parking_assets")

class MonthlyBilling(Base):
    __tablename__ = "monthly_billings"

    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("units.id"))
    billing_month = Column(String, index=True) # e.g. 2026-01
    
    base_fee = Column(Integer, default=0)
    car_cleaning_fee = Column(Integer, default=0)
    scooter_cleaning_fee = Column(Integer, default=0)
    bike_cleaning_fee = Column(Integer, default=0)
    temp_rent = Column(Integer, default=0)
    
    previous_arrears = Column(Integer, default=0) # Positive means arrears, Negative means prepaid
    total_expected = Column(Integer, default=0)
    
    status = Column(String, default="Unpaid") # Unpaid, Paid, Underpaid, Overpaid

    unit = relationship("Unit", back_populates="monthly_billings")
    reconciliations = relationship("PaymentReconciliation", back_populates="monthly_billing")

class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, index=True)
    tx_date = Column(String) # Storing as string for simplicity since source is varied
    amount = Column(Integer, nullable=False)
    transaction_code = Column(String, index=True) # e.g. C06
    billing_month = Column(String, index=True, nullable=True) # e.g. 2026-01
    category = Column(String, nullable=True) # e.g. 利息收入
    virtual_account = Column(String, nullable=True) # raw virtual account string
    matched_unit_id = Column(Integer, ForeignKey("units.id"), nullable=True) # Null if orphaned
    
    # Store other raw details if necessary
    balance = Column(String, nullable=True)
    details = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    matched_unit = relationship("Unit")
    reconciliations = relationship("PaymentReconciliation", back_populates="bank_transaction")

class PaymentReconciliation(Base):
    __tablename__ = "payment_reconciliations"

    id = Column(Integer, primary_key=True, index=True)
    bank_transaction_id = Column(Integer, ForeignKey("bank_transactions.id"))
    monthly_billing_id = Column(Integer, ForeignKey("monthly_billings.id"))
    allocated_amount = Column(Integer, nullable=False)

    bank_transaction = relationship("BankTransaction", back_populates="reconciliations")
    monthly_billing = relationship("MonthlyBilling", back_populates="reconciliations")
