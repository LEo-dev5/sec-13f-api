import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    구글 Gemini API를 사용하여 포트폴리오를 분석합니다.
    (Flash 모델 실패 시 Pro 모델로 자동 전환)
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ 서버에 GEMINI_API_KEY가 설정되지 않았습니다."

        genai.configure(api_key=api_key)
        
        # 요약 데이터 생성
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
        1. 🎯 **투자 테마**: 이 기관의 집중 섹터나 전략 (한 문장)
        2. 🚀 **주목할 변화**: 눈에 띄는 매수/매도 종목과 그 의도 추론
        3. 💡 **인사이트**: 개인 투자자가 참고할 점
        
        (300자 이내, 친절한 해요체 사용)
        """

        # 🚨 [핵심] 모델 시도 로직 (Flash -> Pro 순서)
        models_to_try = ['gemini-1.5-flash', 'gemini-pro']
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                print(f"⚠️ {model_name} 실패: {e}")
                continue # 다음 모델 시도

        return "AI 분석을 생성할 수 없습니다. (모든 모델 실패)"

    except Exception as e:
        return f"AI 연결 오류: {str(e)[:50]}..."