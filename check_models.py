# check_models.py (최신 google-genai 라이브러리 호환)
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ API 키가 없습니다. .env 파일을 확인하세요.")
else:
    print(f"🔑 현재 적용된 API Key: ...{api_key[-4:]}") # 키 뒷자리 확인
    
    try:
        client = genai.Client(api_key=api_key)
        print("\n📋 [내 키로 사용 가능한 모델 목록]")
        print("-" * 40)
        
        # 새 라이브러리에서는 속성 이름이 다를 수 있으므로 안전하게 이름만 출력
        count = 0
        for m in client.models.list():
            # 모델 이름에 'gemini'가 포함된 것만 필터링해서 보기 좋게 출력
            if "gemini" in m.name:
                print(f"✅ {m.name}")
                count += 1
                
        if count == 0:
            print("⚠️ 'gemini' 모델이 하나도 안 보입니다. API 키 설정을 확인하세요.")
            
        print("-" * 40)
        
    except Exception as e:
        print(f"🔥 목록 조회 실패: {e}")
        print("👉 팁: API 키가 올바른지, Google AI Studio에서 'Get API key'를 다시 확인하세요.")