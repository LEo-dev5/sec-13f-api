import httpx

# 설정 (기존과 동일)
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.1:latest"

async def translate_wiki_to_korean(english_text: str) -> str:
    """
    [기업 프로필 생성기 - 강제 치환 전략]
    - AI가 '회사명'을 건드리지 못하게 하고, 지명 번역 예시를 구체적으로 줍니다.
    """
    if not english_text: return ""
    
    # 🚨 AI에게 번역 예시를 떠먹여줍니다.
    prompt = f"""
    Task: Extract key facts from the text and write a profile in Korean.
    Input Text: "{english_text}"
    
    [Rules]
    1. **Structure**: 
       - [Company Name] is a [Industry]. (Do not translate Company Name)
       - Headquarters: [City_Korean], [State_Korean]
       - CEO: [Name_English] (Do not translate Name)
       
    2. **Translation Guide (City/State)**:
       - Omaha -> 오마하
       - Nebraska -> 네브래스카
       - California -> 캘리포니아
       - New York -> 뉴욕
       - Do NOT use phonetic pronunciation like '옴아하'. Use standard Korean names.
    
    3. **Output Example**:
       "Berkshire Hathaway는 미국의 다국적 지주회사입니다. 본사는 네브래스카주 오마하에 있으며, CEO는 Warren Buffett입니다."
       
    4. **Constraint**: Output ONLY the final Korean text.
    """
    
    try:
        payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OLLAMA_URL, json=payload)
            if response.status_code == 200:
                raw_text = response.json().get("response", "").strip()
                
                # 사족 제거 (Here is...)
                if ":" in raw_text and len(raw_text.split(":", 1)[0]) < 20:
                     raw_text = raw_text.split(":", 1)[1].strip()
                
                # 따옴표 제거
                raw_text = raw_text.replace('"', '')
                
                return raw_text
    except Exception as e:
        print(f"프로필 생성 에러: {e}")
        return english_text
    return english_text

async def analyze_portfolio_by_llm(holdings: list, institution_name: str) -> str:
    """
    [포트폴리오 분석]
    - 매도(Selling)와 하락(Drop) 구분 교육 🎓
    """
    # 데이터 텍스트로 변환 (변동률 포함)
    holdings_text = ""
    for h in holdings[:5]: # Top 5만 분석
        name = h.get('name_of_issuer', 'Unknown')
        val = h.get('value', 0)
        change = h.get('change_rate', 0)
        
        # AI가 이해하기 쉽게 문장으로 설명해줌
        action = "SOLD" if change < 0 else "BOUGHT"
        holdings_text += f"- {name}: ${val:,} (Change: {change}% -> {action} {abs(change)}% of shares)\n"

    # 🚨 [핵심] 분석가 페르소나 및 주의사항 설정
    prompt = f"""
    Role: Professional Hedge Fund Analyst.
    Task: Analyze the recent portfolio changes of '{institution_name}' based on the Top Holdings data below.

    [Top Holdings Data]
    {holdings_text}

    [Analysis Guidelines - READ CAREFULLY]
    1. **Interpret Negative Change Correctly**: 
       - If 'Change' is negative (e.g., -14%), it means the fund **SOLD shares** (Profit Taking / Rebalancing).
       - It does **NOT** mean the stock price dropped. 
       - Do **NOT** say the company is "risky" or "unstable" just because they sold shares. Selling is a strategic move.
    
    2. **Style Rules**:
       - Language: Korean (Business Professional).
       - No Introduction: Start analysis immediately. (No "Berkshire is...")
       - Length: 3-4 concise sentences.
       
    3. **Example Output**:
       "애플(Apple Inc)의 비중을 14% 축소하며 차익 실현에 나선 점이 돋보입니다. 이는 특정 종목에 대한 의존도를 낮추고 포트폴리오를 재조정하려는 전략으로 해석됩니다."
    """

    try:
        payload = {"model": MODEL_NAME, "prompt": prompt, "stream": False, "temperature": 0.2}
        print(f"🚀 AI 분석 요청 (New Logic): {institution_name}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OLLAMA_URL, json=payload)
            if response.status_code == 200:
                return clean_ai_output(response.json().get("response", ""))
            return "AI 분석 서버 오류"
    except Exception as e:
        print(f"🔥 AI 에러: {e}")
        return "분석 실패"

def clean_ai_output(text: str) -> str:
    return text.replace("Here is", "").replace("Analysis:", "").replace('"', '').strip()