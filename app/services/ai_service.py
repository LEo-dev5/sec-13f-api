import httpx
import wikipedia
import re
import asyncio

# 1. 로컬 Ollama 설정 (내 컴퓨터)
# 404 에러? 429 에러? 그런 거 없습니다. 무조건 연결됩니다.
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:latest" # 터미널에서 ollama list로 확인한 이름

def get_wiki_summary(query: str) -> str:
    """위키백과에서 정확한 정보를 가져옵니다 (영어 데이터가 풍부함)"""
    try:
        wikipedia.set_lang("en")
        # 'investment firm'을 붙여서 금융 회사로 한정지어 검색
        search_res = wikipedia.search(query + " investment firm", results=1)
        if not search_res: return ""
        # 상위 5문장만 요약
        return wikipedia.summary(search_res[0], sentences=5)
    except: return ""

def clean_ai_output(text: str) -> str:
    """
    라마가 가끔 뱉는 영어 잡담(Here is the translation...)을 삭제하고
    순수 한국어만 남기는 필터링 함수
    """
    lines = text.split('\n')
    korean_lines = []
    for line in lines:
        # 한국어가 포함된 줄만 살림
        if re.search(r'[가-힣]', line):
            # 불필요한 접두사 제거
            cleaned = re.sub(r'^(Translation|Note|Answer):', '', line, flags=re.IGNORECASE).strip()
            # 마크다운 기호 제거
            cleaned = cleaned.replace('**', '').replace('"', '')
            korean_lines.append(cleaned)
            
    result = ' '.join(korean_lines)
    # 만약 필터링했더니 내용이 없으면 원본 반환 (안전장치)
    if len(result) < 10: return text
    return result

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    [로컬 라마 부활] RAG 기술을 적용하여 환각 증세를 치료한 버전
    """
    try:
        # 1. 이름 정제 및 위키백과 검색 (지식 주입) 💉
        clean_name = institution_name.replace(" Inc", "").replace(" Corp", "").replace(" L.P.", "").strip()
        wiki_context = get_wiki_summary(clean_name)
        
        # 2. 보유 종목 정리
        holdings_text = ""
        for h in holdings[:5]:
            name = h.get('name_of_issuer', 'Unknown') if isinstance(h, dict) else getattr(h, 'name_of_issuer', 'Unknown')
            holdings_text += f"- {name}\n"

        # 3. 프롬프트 (강력한 최면 걸기)
        # 위키백과 내용을 근거로 번역하라고 시키면 "버클리" 같은 실수를 안 합니다.
        # 3. 프롬프트 (기업 분석가 모드로 변경)
        # "선생님", "위대한" 같은 감정적 표현을 금지하고, 비즈니스 팩트 위주로 작성하도록 지시
        prompt = f"""
        Role: Corporate Strategy Analyst.
        Task: Write a concise corporate profile for '{institution_name}' in Korean based on the Context.

        [Context (Source)]
        {wiki_context}

        [Top Holdings]
        {holdings_text}

        [Strict Guidelines]
        1. **Focus on Business**: Describe the company's main business model, sector focus, and investment strategy.
        2. **Exclude Biography**: Do NOT mention the founder's birth date, parents, childhood, or personal life. (e.g., No "born in Omaha", No "Howard Buffett").
        3. **Tone**: Dry, Professional, and Objective. (Financial Report style).
           - ❌ Bad: "위대한 리더 버핏 선생님께서..."
           - ⭕ Good: "버크셔 해서웨이는 보험 및 재보험업을 주력으로 하는 지주회사입니다."
        4. **Language Rules**:
           - Use formal Korean business tone (~입니다).
           - Translate 'Berkshire Hathaway' to '버크셔 해서웨이'.
           - Translate 'Warren Buffett' to '워런 버핏'.
        """

        # 4. Ollama에 요청 (비용 0원)
        payload = {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.1 # 0에 가까울수록 창의성 제거 (팩트만 말함)
        }

        print(f"🚀 로컬 라마에게 요청 중... ({clean_name})")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OLLAMA_URL, json=payload)
            
            if response.status_code == 200:
                result_json = response.json()
                raw_text = result_json.get("response", "")
                
                # 5. 영어 잡담 제거 및 출처 표기
                final_text = clean_ai_output(raw_text)
                
                if wiki_context:
                    final_text += "<br><br><span class='text-xs text-gray-400'>ℹ️ 출처: Wikipedia & Local AI</span>"
                
                return final_text
            else:
                return "<div class='text-gray-400 text-sm'>로컬 AI 응답 오류</div>"

    except Exception as e:
        print(f"🔥 로컬 AI 에러: {e}")
        return f"<div class='text-gray-400 text-sm'>AI 서버가 꺼져있거나 응답하지 않습니다.<br>(터미널에서 'ollama serve' 확인)</div>"