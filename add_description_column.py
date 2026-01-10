# add_description_column.py
import sqlite3

DB_FILE = "13f_data.db" # 파일명 확인!

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

try:
    print("🛠️ DB 업그레이드 시작 (description 컬럼 추가)...")
    cursor.execute("ALTER TABLE institutions ADD COLUMN description TEXT")
    conn.commit()
    print("✅ 성공! 'description' 컬럼이 추가되었습니다.")
except sqlite3.OperationalError as e:
    print(f"ℹ️ 알림: {e}")

conn.close()