# reset_cache.py
import sqlite3

# DB 파일 연결
conn = sqlite3.connect("13f_data.db")
cursor = conn.cursor()

try:
    print("🧹 데이터베이스 청소 중...")
    
    # 1. 엉뚱하게 저장된 AI 분석글 삭제 (NULL로 초기화)
    cursor.execute("UPDATE institutions SET ai_summary = NULL")
    
    # 2. 영어로 저장된 기업 개요 삭제 (다시 번역하기 위해)
    cursor.execute("UPDATE institutions SET description = NULL")
    
    conn.commit()
    print("✨ 완료! 모든 캐시가 삭제되었습니다. (새로고침하면 다시 분석합니다)")

except Exception as e:
    print(f"🔥 에러: {e}")
finally:
    conn.close()