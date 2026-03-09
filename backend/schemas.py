from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class UnitBase(BaseModel):
    unit_code: str
    address: Optional[str] = None
    floor: Optional[str] = None
    virtual_account_code: Optional[str] = None

class UnitCreate(UnitBase):
    pass

class Unit(UnitBase):
    id: int

    class Config:
        from_attributes = True

class ResidentBase(BaseModel):
    name: str
    role: Optional[str] = None
    move_in_date: Optional[date] = None
    move_out_date: Optional[date] = None

class Resident(ResidentBase):
    id: int
    unit_id: int

    class Config:
        from_attributes = True

class ParkingAssetBase(BaseModel):
    type: str
    asset_number: Optional[str] = None
    cleaning_fee: int = 0

class ParkingAsset(ParkingAssetBase):
    id: int
    unit_id: int

    class Config:
        from_attributes = True

class MonthlyBillingBase(BaseModel):
    billing_month: str
    base_fee: int = 0
    car_cleaning_fee: int = 0
    scooter_cleaning_fee: int = 0
    bike_cleaning_fee: int = 0
    temp_rent: int = 0
    previous_arrears: int = 0
    total_expected: int = 0
    status: str = "Unpaid"

class MonthlyBilling(MonthlyBillingBase):
    id: int
    unit_id: int

    class Config:
        from_attributes = True

# Composite Schema for the Frontend Master Data Grid
class HouseholdRecordSchema(BaseModel):
    id: int
    unit_code: str
    order: int
    address: Optional[str]
    floor: Optional[str]
    virtual_account_code: Optional[str]
    name: Optional[str] # Primary resident
    
    car_parking: str
    scooter_parking: str
    bike_parking: str
    
    base_fee: int
    car_cleaning_fee: int
    scooter_cleaning_fee: int
    bike_cleaning_fee: int
    temp_rent: int
    
    expected: int # Corresponding to total_expected + previous_arrears
    paid: int # Computed based on payment_reconciliations
    status: str # Overall status

    class Config:
        from_attributes = True

class HouseholdRecordUpdate(BaseModel):
    name: Optional[str] = None
    car_parking: Optional[str] = None
    scooter_parking: Optional[str] = None
    bike_parking: Optional[str] = None
    base_fee: Optional[int] = None
    car_cleaning_fee: Optional[int] = None
    scooter_cleaning_fee: Optional[int] = None
    bike_cleaning_fee: Optional[int] = None
    temp_rent: Optional[int] = None
    expected: Optional[int] = None
    paid: Optional[int] = None
