# app/services/ticker_service.py
import httpx
import re
import difflib # 👈 파이썬 내장 라이브러리 (설치 필요 없음)

# 1. 수동 매핑 (ETF나 이름이 특이한 것들 강제 지정)
# SEC 리스트에 없거나 이름이 너무 달라서 못 찾는 것들은 여기에 추가하세요.
MANUAL_MAP = {
    "SCION ASSET MANAGEMENT": "SCION", # 마이클 버리 펀드 자체
    "BERKSHIRE HATHAWAY": "BRK.B",
    "FACEBOOK": "META",
    "META PLATFORMS": "META",
    "GOOGLE": "GOOGL",
    "ALPHABET": "GOOGL",
    
    # 주요 ETF (13F 보고서에 자주 나오지만 SEC 리스트에 없을 수 있음)
    "SPDR S&P 500 ETF TRUST": "SPY",
    "INVESCO QQQ TRUST": "QQQ",
    "ISHARES TRUST": "IVV", # 주의: iShares는 종류가 많아서 부정확할 수 있음
    "VANGUARD INDEX FUNDS": "VTI",
    "PROSHARES TRUST": "TQQQ",
    "VANECK VECTORS ETF TRUST": "SMH",
    "SPDR GOLD TRUST": "GLD"
}

# 메모리 캐시
SEC_TICKER_MAP = {} # { "정제된이름": "TICKER" }
RAW_NAME_LIST = []  # difflib 검색용 이름 리스트

HEADERS = {
    "User-Agent": "Easy13F_Analyzer/1.0 (kang203062@gmail.com)",
    "Accept-Encoding": "gzip, deflate"
}

async def load_sec_tickers():
    global SEC_TICKER_MAP, RAW_NAME_LIST
    url = "https://www.sec.gov/files/company_tickers.json"
    
    print("📥 [System] 최신 티커 정보 다운로드 및 인덱싱 중...")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=HEADERS, timeout=10.0)
            if resp.status_code != 200:
                print("⚠️ 티커 다운로드 실패. 기본 데이터만 사용합니다.")
                return

            data = resp.json()
            new_map = {}
            raw_names = []
            
            for key, val in data.items():
                title = val['title']
                ticker = val['ticker']
                
                # 1. 원본 이름 저장 (검색용)
                new_map[clean_string(title)] = ticker
                raw_names.append(clean_string(title))
            
            # 수동 맵 병합
            for name, ticker in MANUAL_MAP.items():
                clean_k = clean_string(name)
                new_map[clean_k] = ticker
                raw_names.append(clean_k)

            SEC_TICKER_MAP = new_map
            RAW_NAME_LIST = raw_names
            
            print(f"✅ [System] {len(SEC_TICKER_MAP)}개 종목 인덱싱 완료! (유사도 검색 준비됨)")
            
        except Exception as e:
            print(f"⚠️ 티커 로드 에러: {e}")

def get_ticker_by_name(raw_name: str) -> str:
    """
    3단계 매칭 시스템: 정확 일치 -> 부분 일치 -> 유사도 검색
    """
    if not raw_name: return ""
    
    # 0. 전처리
    target = clean_string(raw_name)
    
    # 1단계: 정확히 일치하는 경우 (Fast)
    if target in SEC_TICKER_MAP:
        return SEC_TICKER_MAP[target]
    
    # 2단계: 수동 매핑 확인 (ETF 등)
    for k, v in MANUAL_MAP.items():
        if k in target or target in k: # "BERKSHIRE HATHAWAY INC" -> "BERKSHIRE HATHAWAY" 포함
            return v
            
    # 3단계: 유사도 검색 (Slow but Powerful) 🐢
    # difflib을 사용하여 가장 비슷한 이름 찾기 (유사도 0.8 이상만)
    matches = difflib.get_close_matches(target, RAW_NAME_LIST, n=1, cutoff=0.85)
    
    if matches:
        best_match = matches[0]
        # print(f"🔍 [Fuzzy Match] {raw_name} -> {best_match} -> {SEC_TICKER_MAP[best_match]}")
        return SEC_TICKER_MAP[best_match]
        
    return ""

def clean_string(text: str) -> str:
    if not text: return ""
    text = text.upper()
    
    # 특수문자 제거
    text = re.sub(r'[^\w\s]', '', text)
    
    # 불필요한 법인 식별자 제거 (뒤에서부터 자름)
    suffixes = [" INC", " CORP", " LTD", " PLC", " SA", " LLC", " LP", " CO", " COMPANY", " LIMITED", " AG", " NV"]
    for s in suffixes:
        if text.endswith(s):
            text = text[:-len(s)]
            
    return text.strip()