import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    구글 AI 모델을 호출합니다.
    전략: 최신 모델(Flash)을 먼저 시도하고, 실패하면 안정적인 구형 모델(Pro)로 자동 전환합니다.
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

        # 4. 요청 보낼 모델 후보군 (순서대로 시도)
        # Flash: 빠르고 최신 / Pro: 조금 느리지만 가장 안정적
        models = [
            "gemini-1.5-flash",
            "gemini-pro"
        ]

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            last_error = ""
            
            for model_name in models:
                try:
                    # v1beta 엔드포인트 사용
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                    
                    # 요청 전송
                    resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
                    
                    # 성공(200)하면 바로 결과 리턴하고 끝냄
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return text
                    
                    # 실패하면 로그 찍고 다음 모델 시도
                    error_msg = resp.text
                    print(f"⚠️ {model_name} 실패 (Status: {resp.status_code}): {error_msg}")
                    last_error = f"{model_name} Error: {resp.status_code}"
                    
                except Exception as e:
                    print(f"⚠️ {model_name} 연결 오류: {e}")
                    last_error = str(e)
                    continue

            # 모든 모델이 실패했을 경우
            return f"AI 분석 서버가 응답하지 않습니다. ({last_error})"

    except Exception as e:
        print(f"🔥 AI Request Error: {e}")
        return "AI 연결 중 오류 발생"