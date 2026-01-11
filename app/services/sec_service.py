import httpx
import asyncio
from sqlalchemy.orm import Session
from app.db.models import Institution, Holding
from app.services.stock_service import get_stock_price
import re

# 🚨 [중요] SEC는 이 헤더(User-Agent)가 없으면 접속을 차단합니다.
SEC_HEADERS = {
    "User-Agent": "Easy13F_Analyzer/1.0 (kang203062@gmail.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}

async def fetch_all_13f_ciks(year: int, quarter: int) -> list:
    """
    SEC의 분기별 마스터 인덱스 파일(master.idx)을 다운로드해서
    '13F-HR' 공시를 낸 기관들의 CIK 명단을 추출합니다.
    """
    # 2025년 3분기 Index 파일 주소
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
    print(f"📡 SEC 명단 다운로드 시도: {url}")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        # 1. 파일 다운로드 요청
        resp = await client.get(url, headers=SEC_HEADERS)
        
        if resp.status_code != 200:
            print(f"🔥 SEC 접속 실패 ({resp.status_code}): 차단되었거나 주소가 잘못됨")
            return []
        
        # 2. 데이터 파싱 (복잡한 텍스트 파일에서 '13F-HR'만 골라내기)
        content = resp.text
        ciks = set()
        
        # 정규표현식으로 13F-HR 라인 찾기
        # 형식: CIK | Company Name | Form Type | Date | Filename
        for line in content.split('\n'):
            if "13F-HR" in line:
                try:
                    # 파이프(|)로 구분된 데이터 쪼개기
                    parts = line.split('|')
                    if len(parts) > 4:
                        cik = parts[0].strip()
                        ciks.add(cik)
                except:
                    continue
                    
        print(f"✅ 명단 확보 완료: 총 {len(ciks)}개 기관 발견")
        return list(ciks)

async def fetch_13f_holdings(cik: str):
    """
    특정 기관(CIK)의 최신 13F 포트폴리오 데이터를 XML로 가져옵니다.
    """
    # 1. 기관의 최신 공시 목록 가져오기
    browse_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            resp = await client.get(browse_url, headers=SEC_HEADERS)
            if resp.status_code != 200: return []
            
            data = resp.json()
            filings = data.get("filings", {}).get("recent", {})
            
            # 최신 13F-HR 찾기
            accession_num = None
            primary_doc = None
            
            for i, form in enumerate(filings.get("form", [])):
                if form == "13F-HR":
                    accession_num = filings["accessionNumber"][i] # 예: 0001067983-23-000001
                    primary_doc = filings["primaryDocument"][i]   # 예: form13fInfoTable.xml
                    break
            
            if not accession_num: return []

            # 2. XML 데이터 주소 조합
            # 대시(-) 제거: 0001067983-23-000001 -> 000106798323000001
            clean_accession = accession_num.replace("-", "")
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{clean_accession}/{primary_doc}"
            
            # 3. XML 다운로드
            xml_resp = await client.get(xml_url, headers=SEC_HEADERS)
            if xml_resp.status_code != 200: return []
            
            # 4. XML 파싱 (간단하게 정규표현식 사용)
            xml_text = xml_resp.text
            holdings = []
            
            # <nameOfIssuer>애플</nameOfIssuer> ... <value>1000</value> 패턴 찾기
            # (실제 SEC XML 구조에 맞춰 단순화한 파서입니다)
            issuer_matches = re.findall(r'<nameOfIssuer>(.*?)</nameOfIssuer>', xml_text, re.DOTALL)
            ticker_matches = re.findall(r'<sshPrnamtType>.*?</sshPrnamtType>.*?<cusip>(.*?)</cusip>', xml_text, re.DOTALL) 
            # cusip 대신 ticker가 있으면 좋지만, 보통 XML엔 CUSIP만 있는 경우가 많음.
            # 여기선 간편하게 value와 sshPrnamt(주식수) 위주로 추출
            
            # 정교한 파싱을 위해 BeautifulSoup 대신 문자열 split 방식 사용 (속도 최적화)
            info_tables = xml_text.split('<infoTable>')
            
            for table in info_tables[1:]: # 첫 번째 덩어리는 헤더이므로 제외
                try:
                    name = re.search(r'<nameOfIssuer>(.*?)</nameOfIssuer>', table).group(1)
                    value = int(re.search(r'<value>(.*?)</value>', table).group(1))
                    shares = int(re.search(r'<sshPrnamt>(.*?)</sshPrnamt>', table).group(1))
                    
                    # 티커 찾기 (없으면 이름으로 대체하거나 CUSIP 사용)
                    # 여기서는 간단히 이름의 첫 단어를 티커처럼 사용하거나, 별도 매핑 필요
                    # (실제론 CUSIP -> Ticker 변환이 필요하나, 일단 이름으로 저장)
                    ticker_match = re.search(r'<cusip>(.*?)</cusip>', table)
                    ticker = ticker_match.group(1) if ticker_match else name[:4].upper()

                    holdings.append({
                        "name": name,
                        "ticker": ticker, 
                        "value": value * 1000, # 단위가 $1000일 수 있음 (보통 13F는 1000단위 아님, 그대로 사용)
                        "shares": shares
                    })
                except:
                    continue
                    
            return holdings

        except Exception as e:
            print(f"Error fetching holdings for {cik}: {e}")
            return []