import os
from google import genai # 🚨 라이브러리 변경됨
from dotenv import load_dotenv

load_dotenv()

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    구글의 최신 SDK(google-genai)를 사용하여 포트폴리오를 분석합니다.
    """
    try:
        # 1. API 키 확인
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ 서버에 GEMINI_API_KEY가 설정되지 않았습니다."

        # 2. 클라이언트 초기화 (신버전 방식)
        client = genai.Client(api_key=api_key)

        # 3. 데이터 요약
        summary_text = ""
        for h in holdings[:15]: 
            name = h.get('name_of_issuer', 'Unknown')
            val = h.get('value', 0)
            chg = h.get('change_rate', 0)
            summary_text += f"- {name}: ${val:,} ({chg}%)\n"

        # 4. 프롬프트 작성
        prompt = f"""
        당신은 월스트리트의 시니어 퀀트 애널리스트입니다.
        투자 기관 '{institution_name}'의 최신 포트폴리오를 분석해주세요.

        [데이터]
        {summary_text}

        [분석 항목]
        1. 🎯 **투자 테마**: 이 기관의 집중 섹터나 전략 (한 문장)
        2. 🚀 **주목할 변화**: 눈에 띄는 매수/매도 종목과 그 의도 추론
        3. 💡 **인사이트**: 개인 투자자가 참고할 점
        
        (300자 이내, 친절한 해요체 사용)
        """

        # 5. AI 요청 (신버전 방식)
        # gemini-1.5-flash 모델 사용
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        
        if response and response.text:
            return response.text
        else:
            return "AI가 답변을 생성하지 못했습니다."

    except Exception as e:
        print(f"🔥 Gemini AI Error: {e}")
        return f"AI 분석 서비스 연결 오류: {str(e)[:50]}..."