import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    [진단 모드]
    1. v1beta와 v1 엔드포인트를 모두 시도합니다.
    2. 실패 시, 현재 API 키로 사용 가능한 모델 목록을 조회하여 로그에 남깁니다.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ API 키가 없습니다."

        # 데이터 요약
        summary_text = ""
        for h in holdings[:15]: 
            name = h.get('name_of_issuer', 'Unknown')
            val = h.get('value', 0)
            chg = h.get('change_rate', 0)
            summary_text += f"- {name}: ${val:,} ({chg}%)\n"

        prompt = f"""
        당신은 월스트리트의 시니어 퀀트 애널리스트입니다.
        투자 기관 '{institution_name}'의 최신 포트폴리오를 분석해주세요.
        
        [데이터]
        {summary_text}
        
        [분석 항목]
        1. 🎯 **투자 테마**: (한 문장)
        2. 🚀 **주목할 변화**: (매수/매도 특징)
        3. 💡 **인사이트**: (개인 투자자 참고점)
        
        (300자 이내, 친절한 해요체)
        """

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        # 🚨 [전략] 사용 가능한 모든 주소와 모델을 순서대로 때려봅니다.
        # v1beta (최신) -> v1 (안정) 순서
        endpoints = [
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}",
            f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={api_key}", # v1 안정 버전
        ]

        async with httpx.AsyncClient(timeout=30.0) as client:
            for url in endpoints:
                try:
                    resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
                    else:
                        print(f"⚠️ 실패 ({url}): {resp.status_code} - {resp.text}")
                except Exception as e:
                    print(f"⚠️ 연결 오류: {e}")
                    continue

            # 🚨 [최후의 수단] 도대체 무슨 모델이 있는지 명단 요청 (List Models)
            print("🔥 모든 시도 실패. 사용 가능한 모델 목록을 조회합니다...")
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            list_resp = await client.get(list_url)
            
            if list_resp.status_code == 200:
                models = list_resp.json().get('models', [])
                available_names = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
                print(f"✅ [진단 결과] 사용 가능한 모델 명단: {available_names}")
                return f"설정 오류입니다. 로그를 확인하세요. (사용 가능 모델: {len(available_names)}개)"
            else:
                print(f"❌ 모델 목록 조회도 실패: {list_resp.text}")
                return "API 키 권한이 없거나 구글 계정 설정 문제입니다."

    except Exception as e:
        print(f"🔥 System Error: {e}")
        return "AI 시스템 오류"