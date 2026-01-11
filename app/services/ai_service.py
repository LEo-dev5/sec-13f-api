import os
import httpx
from dotenv import load_dotenv

load_dotenv()

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    구글 라이브러리를 쓰지 않고, REST API로 직접 요청합니다. (가장 확실한 방법)
    """
    try:
        # 1. API 키 확인
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ 서버에 GEMINI_API_KEY가 설정되지 않았습니다."

        # 2. 데이터 요약
        summary_text = ""
        for h in holdings[:15]: 
            name = h.get('name_of_issuer', 'Unknown')
            val = h.get('value', 0)
            chg = h.get('change_rate', 0)
            summary_text += f"- {name}: ${val:,} ({chg}%)\n"

        # 3. 프롬프트 작성
        prompt = f"""
        당신은 월스트리트의 시니어 퀀트 애널리스트입니다.
        투자 기관 '{institution_name}'의 최신 포트폴리오를 분석해주세요.

        [데이터]
        {summary_text}

        [분석 항목]
        1. 🎯 **투자 테마**: 이 기관의 집중 섹터나 전략 (한 문장)
        2. 🚀 **주목할 변화**: 눈에 띄는 매수/매도 종목과 그 의도 추론
        3. 💡 **인사이트**: 개인 투자자가 참고할 점
        
        (300자 이내, 친절한 해요체 사용, 마크다운 형식 금지)
        """

        # 4. 직접 URL 호출 (라이브러리 의존성 제거)
        # gemini-1.5-flash 모델의 REST API 주소입니다.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            
            if resp.status_code != 200:
                print(f"🔥 Google API Error: {resp.text}")
                # 혹시 Flash 모델이 안되면 Pro 모델로 재시도
                if "not found" in resp.text or resp.status_code == 404:
                     url_pro = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
                     resp = await client.post(url_pro, json=payload, headers={"Content-Type": "application/json"})
                     if resp.status_code != 200:
                         return "AI 서버가 응답하지 않습니다."
                else:
                    return f"AI 오류 ({resp.status_code})"

            data = resp.json()
            # 응답 파싱
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text
            except (KeyError, IndexError):
                return "AI가 답변을 생성하지 못했습니다."

    except Exception as e:
        print(f"🔥 AI Request Error: {e}")
        return f"AI 연결 중 오류 발생: {str(e)[:30]}..."