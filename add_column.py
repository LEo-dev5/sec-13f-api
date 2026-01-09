# add_column.py
import sqlite3

# DB 파일 이름이 '13f_data.db'라고 가정합니다. (다르면 수정하세요)
DB_FILE = "13f_data.db"

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

try:
    print("🛠️ DB 업그레이드 시작...")
    # institutions 테이블에 ai_summary 컬럼 추가
    cursor.execute("ALTER TABLE institutions ADD COLUMN ai_summary TEXT")
    conn.commit()
    print("✅ 성공! 'ai_summary' 컬럼이 추가되었습니다.")
except sqlite3.OperationalError as e:
    print(f"ℹ️ 알림: {e}")
    print("   (이미 컬럼이 존재하거나 문제가 없습니다.)")
finally:
    conn.close()