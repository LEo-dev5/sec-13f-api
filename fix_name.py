# fix_name.py
import sqlite3

conn = sqlite3.connect("13f_data.db")
cursor = conn.cursor()

try:
    print("🩹 데이터베이스 수술 중...")
    
    # 1. 버크셔 해서웨이(CIK: 0001067983) 이름 강제 주입
    cursor.execute("""
        UPDATE institutions 
        SET name = 'Berkshire Hathaway Inc' 
        WHERE cik = '0001067983'
    """)
    
    # 2. 혹시 이름이 없는 다른 친구들도 확인
    cursor.execute("SELECT cik FROM institutions WHERE name IS NULL OR name = ''")
    ghosts = cursor.fetchall()
    
    if ghosts:
        print(f"⚠️ 이름 없는 유령 데이터가 {len(ghosts)}개 더 있습니다.")
        # (원한다면 여기서 삭제하거나 수정 가능)
    
    conn.commit()
    print("✨ 수술 완료! 이제 제목이 잘 뜰 겁니다.")

except Exception as e:
    print(f"🔥 에러: {e}")
finally:
    conn.close()