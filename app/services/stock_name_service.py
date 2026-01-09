# app/services/stock_name_service.py

# 자주 쓰이는 종목들의 SEC 이름 -> 사람이 부르는 이름 매핑
# (실제 서비스에서는 DB나 외부 API를 쓰지만, 여기서는 주요 종목 하드코딩으로 해결)
TICKER_MAP = {
    "APPLE INC": ("애플", "AAPL"),
    "AMERICAN EXPRESS CO": ("아메리칸 익스프레스", "AXP"),
    "BANK AMER CORP": ("뱅크오브아메리카", "BAC"),
    "COCA COLA CO": ("코카콜라", "KO"),
    "CHEVRON CORP NEW": ("쉐브론", "CVX"),
    "OCCIDENTAL PETE CORP": ("옥시덴탈", "OXY"),
    "MOODYS CORP": ("무디스", "MCO"),
    "CHUBB LIMITED": ("처브", "CB"), # 보험사
    "KRAFT HEINZ CO": ("크래프트 하인즈", "KHC"),
    "ALPHABET INC": ("구글(알파벳)", "GOOGL"),
    "DAVITA INC": ("다비타", "DVA"),
    "KROGER CO": ("크로거", "KR"),
    "SIRIUS XM HOLDINGS INC": ("시리우스 XM", "SIRI"),
    "VISA INC": ("비자", "V"),
    "VERISIGN INC": ("베리사인", "VRSN"),
    "MASTERCARD INC": ("마스터카드", "MA"),
    "AMAZON COM INC": ("아마존", "AMZN"),
}

def normalize_name(sec_name: str) -> tuple[str, str]:
    """
    SEC 이름을 받아서 (한글명, 티커) 튜플을 반환합니다.
    없으면 그냥 (원래이름, '') 반환
    """
    # 정확히 일치하는 경우
    if sec_name in TICKER_MAP:
        return TICKER_MAP[sec_name]
    
    # 부분 일치 (예: AMAZON COM -> 아마존)
    for key, val in TICKER_MAP.items():
        if key in sec_name:
            return val
            
    return sec_name.title(), "" # 매핑 없으면 첫글자만 대문자로