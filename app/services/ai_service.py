import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    구글 Gemini API를 사용하여 포트폴리오를 분석합니다.
    """
    try:
        # 1. API 키 확인
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ AI 분석을 위한 API 키(GEMINI_API_KEY)가 서버에 설정되지 않았습니다."

        # 2. Gemini 설정
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')

        # 3. 데이터 요약 (토큰 절약을 위해 상위 10개만)
        summary_text = ""
        for h in holdings[:10]: 
            name = h.get('name_of_issuer', 'Unknown')
            value = h.get('value', 0)
            change = h.get('change_rate', 0)
            summary_text += f"- {name}: ${value:,} (변동률: {change}%)\n"

        # 4. 프롬프트 작성 (한국어)
        prompt = f"""
        당신은 월스트리트의 전문 금융 애널리스트입니다.
        '{institution_name}'이라는 투자 기관의 최신 포트폴리오 상위 종목을 분석해주세요.

        [보유 종목 데이터]
        {summary_text}

        [요청사항]
        1. 이 기관의 투자 스타일을 한 문장으로 요약하세요. (예: 기술주 중심의 공격적 투자 등)
        2. 가장 눈에 띄는 종목 1~2가지를 언급하고, 왜 샀을지(혹은 팔았을지) 추론해보세요.
        3. 말투는 친절하고 전문적인 '해요체'를 사용하세요. (300자 이내)
        4. 서론 없이 바로 본론으로 들어가세요.
        """

        # 5. AI에게 질문 (비동기 처리 흉내)
        # Gemini 라이브러리는 동기 방식이지만, Render에서는 빨라서 괜찮습니다.
        response = model.generate_content(prompt)
        
        if response.text:
            return response.text
        else:
            return "AI가 답변을 생성하지 못했습니다."

    except Exception as e:
        print(f"🔥 Gemini AI Error: {e}")
        return "죄송합니다. 현재 AI 분석 서비스가 혼잡하여 응답할 수 없습니다."