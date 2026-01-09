# test_env.py
import os
from dotenv import load_dotenv

# 현재 폴더에 있는 .env 파일을 강제로 찾아서 읽음
load_dotenv(verbose=True)

key = os.getenv("GOOGLE_API_KEY")

print("-" * 30)
if key:
    print(f"✅ 성공! 키를 읽었습니다: {key[:10]}...")
else:
    print("❌ 실패! .env 파일을 못 찾거나 키가 없습니다.")
    print(f"현재 폴더 위치: {os.getcwd()}")
    print("현재 폴더 파일 목록:", os.listdir())
print("-" * 30)