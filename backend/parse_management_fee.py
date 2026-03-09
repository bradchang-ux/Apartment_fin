import pandas as pd

def parse_management_fee_sheet(file_path):
    """
    Parses the household management fee tracking sheet.
    Returns a dictionary mapping household unit to expected fee details.
    """
    try:
        xl = pd.ExcelFile(file_path)
        sheet_name = None
        for name in xl.sheet_names:
            if '管理費' in name:
                sheet_name = name
                break
        
        if not sheet_name:
            raise ValueError("Could not find management fee sheet in Excel.")

        # User requested to specifically read rows 4 to 57.
        # skiprows=3 skips rows 1, 2, 3. nrows=54 reads exactly 54 rows (rows 4 to 57).
        df = xl.parse(sheet_name, header=None, skiprows=3, nrows=54)

        households = []
        for index, row in df.iterrows():
            item_id = str(row.iloc[0]).strip()
            if item_id.lower() == 'nan' or not item_id.isdigit():
                continue

            # Basic info
            unit = str(row.iloc[1]).strip()
            floor = str(row.iloc[2]).strip()
            name = str(row.iloc[3]).strip()
            
            # Parking info
            car_parking = str(row.iloc[4]).strip() if str(row.iloc[4]).strip().lower() != 'nan' else ''
            scooter_parking = str(row.iloc[5]).strip() if str(row.iloc[5]).strip().lower() != 'nan' else ''
            bike_parking = str(row.iloc[6]).strip() if str(row.iloc[6]).strip().lower() != 'nan' else ''
            
            # Fees (handle commas and nan)
            def safe_int(val):
                v_str = str(val).replace(',', '').replace('.0', '').strip()
                try: return int(float(v_str)) if v_str.lower() != 'nan' else 0
                except: return 0

            base_fee = safe_int(row.iloc[7])
            car_cleaning_fee = safe_int(row.iloc[8])
            scooter_cleaning_fee = safe_int(row.iloc[9])
            bike_cleaning_fee = safe_int(row.iloc[10])
            temp_rent = safe_int(row.iloc[11])
            expected = safe_int(row.iloc[12]) # Actual 'expected' is at index 12 based on the CSV dump

            households.append({
                "unit": unit,
                "floor": floor,
                "name": name,
                "car_parking": car_parking,
                "scooter_parking": scooter_parking,
                "bike_parking": bike_parking,
                "base_fee": base_fee,
                "car_cleaning_fee": car_cleaning_fee,
                "scooter_cleaning_fee": scooter_cleaning_fee,
                "bike_cleaning_fee": bike_cleaning_fee,
                "temp_rent": temp_rent,
                "expected": expected
            })

        return households

        return households
    except Exception as e:
        print(f"Error parsing management fees: {e}")
        return {}

if __name__ == '__main__':
    res = parse_management_fee_sheet('../11501月財報資料.xlsx')
    print("Found", len(res), "households")
    if res:
       print(res[0])
