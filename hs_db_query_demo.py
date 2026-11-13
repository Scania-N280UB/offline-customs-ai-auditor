import sqlite3
import os
import pandas as pd

def init_db_from_csv(csv_path="hs_codes_sample.csv", db_path="customs_hs_sample.db"):
    """如果数据库表不存在，自动读取 CSV 转换并建立索引"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查 hs_rules 表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='hs_rules';")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        if os.path.exists(csv_path):
            print(f"📦 正在从 {csv_path} 初始化数据库 {db_path}...")
            df = pd.read_csv(csv_path, dtype={'hs_code': str})
            df.to_sql('hs_rules', conn, if_exists='replace', index=False)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hs ON hs_rules(hs_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON hs_rules(goods_name);")
            conn.commit()
            print("✅ 数据库表初始化完成！")
        else:
            print(f"❌ 未找到数据集文件 {csv_path}，无法自动创建数据库！")
            conn.close()
            return False
    conn.close()
    return True

def query_hs_db(db_path="customs_hs_sample.db", hs_code=None, keyword=None):
    # 先确保数据库表已建好
    if not init_db_from_csv(db_path=db_path):
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    results = []
    if hs_code:
        cursor.execute("SELECT * FROM hs_rules WHERE hs_code=?", (str(hs_code).strip(),))
        results = cursor.fetchall()
        print(f"\n🔍 --- 按照 HS Code [{hs_code}] 查询结果 ---")
    
    if keyword:
        cursor.execute("SELECT * FROM hs_rules WHERE goods_name LIKE ?", (f"%{keyword}%",))
        results = cursor.fetchall()
        print(f"\n🔍 --- 按照品名关键词 [{keyword}] 查询结果 ---")
        
    if not results:
        print("⚠️ 未找到匹配的关务监管条件。")
    else:
        for row in results:
            print(f"HS Code: {row[0]}")
            print(f"品名: {row[1]}")
            print(f"监管条件: {row[2] if pd.notna(row[2]) and row[2] else '无'}")
            print(f"检验检疫类别: {row[3] if pd.notna(row[3]) and row[3] else '无'}")
            print("-" * 30)
        
    conn.close()

if __name__ == "__main__":
    db_file = "customs_hs_sample.db"
    
    # 查阅 PBMC / 血液制品的监管条件
    query_hs_db(db_file, hs_code="3002909000")
    
    # 模糊搜索干冰的监管条件
    query_hs_db(db_file, keyword="干冰")
