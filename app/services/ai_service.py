import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    구글 Gemini API (Flash 모델)를 사용하여 포트폴리오를 분석합니다.
    """
    try:
        # 1. API 키 확인
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return "⚠️ 서버에 GEMINI_API_KEY가 설정되지 않았습니다."

        # 2. Gemini 설정 (최신 모델로 변경)
        genai.configure(api_key=api_key)
        
        # 🚨 [수정] gemini-pro -> gemini-1.5-flash (더 빠르고 안정적)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # 3. 데이터 요약 (상위 15개로 늘림)
        summary_text = ""
        for h in holdings[:15]: 
            name = h.get('name_of_issuer', 'Unknown')
            value = h.get('value', 0)
            change = h.get('change_rate', 0)
            summary_text += f"- {name}: ${value:,} (변동: {change}%)\n"

        # 4. 프롬프트 작성
        prompt = f"""
        당신은 월스트리트의 시니어 퀀트 애널리스트입니다.
        투자 기관 '{institution_name}'의 최신 포트폴리오(Top Holdings)를 보고 핵심 전략을 분석해주세요.

        [보유 종목 데이터]
        {summary_text}

        [분석 요청]
        1. 🎯 **투자 테마**: 이 기관이 집중하고 있는 섹터나 전략은 무엇인가요? (한 문장 요약)
        2. 🚀 **주목할 변화**: 가장 눈에 띄는 매수/매도 종목을 언급하고 그 의도를 추론하세요.
        3. 💡 **인사이트**: 개인 투자자가 참고할 만한 점은 무엇인가요?
        
        * 말투: 친절하고 전문적인 '해요체'를 사용하세요.
        * 분량: 300자 내외로 핵심만 간결하게.
        * 형식: 서론 없이 바로 분석 내용을 시작하세요.
        """

        # 5. AI 요청
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text
        else:
            return "AI가 답변을 생성하지 못했습니다."

    except Exception as e:
        print(f"🔥 Gemini AI Error: {e}")
        # 에러 메시지를 좀 더 친절하게 반환
        return f"현재 AI 분석 서버 연결이 지연되고 있습니다. (Error: {str(e)[:50]}...)"