from database import SessionLocal
from models import Unit, MonthlyBilling, Resident

def demonstrate_db_operations():
    # 🌟 步驟 1: 開啟資料庫連線會話 (Session)
    db = SessionLocal()
    print("--- 模擬操作開始 ---\n")

    try:
        # ==========================================
        # 🟢 讀取操作 (READ)
        # ==========================================
        print("1. [查詢資料] 尋找戶號為 A1 的住戶")
        # 使用 SQLAlchemy 的語法進行查詢
        a1_unit = db.query(Unit).filter(Unit.unit_code.like("A1%")).first()
        
        if a1_unit:
            print(f"找到房屋: {a1_unit.address}, 虛擬帳號: {a1_unit.virtual_account_code}")
            
            # 透過 Relationship 幫我們把關聯的「住戶名稱」與「帳單」自動拉出來！
            owners = [r.name for r in a1_unit.residents]
            print(f"屬於該戶的住戶/屋主: {', '.join(owners)}")
            
            # 找出 2026-01 的帳單
            billing = db.query(MonthlyBilling).filter(
                MonthlyBilling.unit_id == a1_unit.id,
                MonthlyBilling.billing_month == "2026-01"
            ).first()
            if billing:
                print(f"2026-01 帳單狀態: 應繳 {billing.total_expected} 元, 狀態為 {billing.status}")
        print()

        # ==========================================
        # 🔵 更新操作 (UPDATE)
        # ==========================================
        print("2. [更新資料] 假設我們要手動幫 A1 的 2026-01 帳單加上 500 元的『其他欠款』")
        if billing:
             # 直接修改 Python 物件的屬性
             billing.previous_arrears += 500
             # 等待 commit() 後就會寫入資料庫
             print(f"修改完成！現在 A1 的累積欠款變成: {billing.previous_arrears} 元")
        print()

        # ==========================================
        # 🟡 新增操作 (CREATE)
        # ==========================================
        print("3. [新增資料] 假設 A1 搬來了一位新租客，我們要加進資料庫")
        new_tenant = Resident(
             unit_id=a1_unit.id,
             name="王小明 (新租客)",
             role="Tenant"
        )
        # 把新物件加入 Session
        db.add(new_tenant)
        print("已將新租客加入待儲存名單 (尚未真正存進 DB)")
        print()

        # ==========================================
        # 🔴 刪除操作 (DELETE) - 示範，但不真的刪除
        # ==========================================
        print("4. [刪除操作] 尋找剛剛新增的租客並準備移除 (模擬用)")
        # 實際刪除的語法是： db.delete(object_to_delete)
        print("語法範例: `db.delete(tenant_to_remove)`")
        print()

        # 🌟 步驟 2: 交易確認 (Commit) 或 取消 (Rollback)
        # 如果你想把剛才的「更新欠款」跟「新增租客」真正寫入檔案，就執行 db.commit()
        # 這裡為了不弄髒您的環境，我們執行 rollback() 取消剛剛的所有操作！
        print("5. [儲存或取消]")
        db.rollback() 
        print("執行 db.rollback()：剛才做的修改與新增都已撤銷，資料庫保持原樣！")
        # 如果要儲存，改成 -> db.commit()

    finally:
        # 🌟 步驟 3: 關閉連線 (非常重要)
        db.close()
        print("\n--- 模擬操作結束 ---")

if __name__ == "__main__":
    demonstrate_db_operations()
