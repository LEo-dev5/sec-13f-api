import httpx
import asyncio
import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import random
import re
from app.schemas.stock import Holding, FilingResponse
from app.services.stock_service import get_stock_price # 주가 조회 서비스 임포트

# 🚨 SEC 차단 방지용 헤더
USER_AGENT = "Easy13F_Project (kang203062@gmail.com)"

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

HEADERS_ARCHIVE = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}

# ---------------------------------------------------------
# 1. [유틸리티] XML 파싱 및 데이터프레임 변환
# ---------------------------------------------------------
def get_empty_df():
    return pd.DataFrame(columns=['name_of_issuer', 'cusip', 'value', 'shares', 'ssh_prnamt_type', 'holding_type'])

def parse_13f_xml_to_dict(xml_content: str) -> list[dict]:
    holdings = []
    try:
        root = ET.fromstring(xml_content)
        for info in root.findall(".//{*}infoTable"):
            try:
                issuer_node = info.find("{*}nameOfIssuer")
                value_node = info.find("{*}value")
                shrs_node = info.find("{*}shrsOrPrnAmt")
                
                if issuer_node is None or value_node is None: continue

                ssh_amt_node = shrs_node.find("{*}sshPrnamt") if shrs_node is not None else None
                ssh_type_node = shrs_node.find("{*}sshPrnamtType") if shrs_node is not None else None
                
                # CUSIP이나 Ticker 찾기
                cusip_node = info.find("{*}cusip")
                cusip = cusip_node.text if cusip_node is not None else "000000000"

                holdings.append({
                    "name_of_issuer": issuer_node.text,
                    "cusip": cusip,
                    "value": int(value_node.text),
                    "shares": int(ssh_amt_node.text) if ssh_amt_node is not None else 0,
                    "ssh_prnamt_type": ssh_type_node.text if ssh_type_node is not None else "SH",
                    "holding_type": "Stock" # 단순화
                })
            except: 
                continue
    except Exception as e:
        print(f"⚠️ XML 파싱 실패: {e}")
    return holdings

async def fetch_holdings_df(client, cik_int, accession_number):
    try:
        acc_no_path = accession_number.replace("-", "")
        # index.json 가져오기
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_path}/index.json"
        
        resp = await client.get(index_url, headers=HEADERS_ARCHIVE)
        if resp.status_code != 200: return get_empty_df()
        
        # XML 파일 찾기
        directory_data = resp.json()
        target_xml = ""
        for item in directory_data['directory']['item']:
            name = item['name'].lower()
            if name.endswith(".xml") and ("infotable" in name or "primary" in name):
                target_xml = item['name']
                if "infotable" in name: break # infoTable이 우선
        
        if not target_xml: return get_empty_df()
        
        # XML 다운로드
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_path}/{target_xml}"
        xml_resp = await client.get(xml_url, headers=HEADERS_ARCHIVE)
        if xml_resp.status_code != 200: return get_empty_df()

        raw_data = parse_13f_xml_to_dict(xml_resp.text)
        if not raw_data: return get_empty_df()
        
        return pd.DataFrame(raw_data)
        
    except Exception:
        return get_empty_df()

# ---------------------------------------------------------
# 2. [기능 A] 전체 기관 명단 가져오기 (Admin용)
# ---------------------------------------------------------
async def fetch_all_13f_ciks(year: int, quarter: int) -> list:
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
    print(f"📡 SEC 명단 다운로드: {url}")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=HEADERS_ARCHIVE)
        if resp.status_code != 200:
            print(f"🔥 SEC 접속 실패 ({resp.status_code})")
            return []
        
        content = resp.text
        ciks = set()
        for line in content.split('\n'):
            if "13F-HR" in line:
                try:
                    parts = line.split('|')
                    if len(parts) > 4:
                        ciks.add(parts[0].strip())
                except: continue
        
        print(f"✅ 명단 확보: {len(ciks)}개")
        return list(ciks)

# ---------------------------------------------------------
# 3. [기능 B] 개별 기관 최신 데이터 가져오기 (검색/상세페이지용)
#    🚨 이 함수가 없어서 에러가 났던 겁니다! 다시 추가했습니다.
# ---------------------------------------------------------
async def fetch_latest_13f(cik: str) -> FilingResponse:
    cik_int = str(int(cik))
    cik_padded = cik.zfill(10)
    submission_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        # 1. 제출 기록 가져오기
        resp = await client.get(submission_url, headers=HEADERS)
        if resp.status_code != 200:
            raise Exception("SEC API 접속 실패")
        
        data = resp.json()
        institution_name = data.get('name', 'Unknown').title()
        
        # 2. 최신 13F-HR 찾기
        filings = data['filings']['recent']
        target_filings = []
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                target_filings.append({
                    'date': filings['reportDate'][i],
                    'acc': filings['accessionNumber'][i]
                })
                if len(target_filings) == 2: break # 이번 분기, 지난 분기 2개만
        
        if not target_filings: raise Exception("13F 보고서 없음")

        # 3. 이번 분기 데이터 가져오기
        df_curr = await fetch_holdings_df(client, cik_int, target_filings[0]['acc'])
        
        # 4. (옵션) 지난 분기 데이터 가져와서 비교
        df_prev = pd.DataFrame()
        if len(target_filings) > 1:
            await asyncio.sleep(0.5) # 예의상 딜레이
            df_prev = await fetch_holdings_df(client, cik_int, target_filings[1]['acc'])

        # 5. 데이터 병합 및 계산
        final_df = df_curr.copy()
        if final_df.empty: return FilingResponse(cik=cik, institution_name=institution_name, report_date="", holdings=[])

        # 변화율 계산 로직
        if 'change_rate' not in final_df.columns: final_df['change_rate'] = 0.0
        if 'prev_shares' not in final_df.columns: final_df['prev_shares'] = 0

        if not df_prev.empty:
            try:
                # 같은 종목(CUSIP)끼리 비교
                merged = pd.merge(
                    df_curr, 
                    df_prev[['cusip', 'shares']], 
                    on=['cusip'],
                    how='left', 
                    suffixes=('', '_prev')
                )
                merged['prev_shares'] = merged['shares_prev'].fillna(0).astype(int)
                
                # (이번 - 지난) / 지난 * 100
                merged['change_rate'] = np.where(
                    merged['prev_shares'] > 0,
                    ((merged['shares'] - merged['prev_shares']) / merged['prev_shares'] * 100),
                    100.0
                )
                # 신규 진입은 100%로 표시
                merged['change_rate'] = merged['change_rate'].replace([np.inf, -np.inf], 100.0)
                final_df = merged
            except: pass

        # 6. 결과 변환 (DataFrame -> List[Holding])
        holdings_list = []
        # 가치 순 정렬
        if 'value' in final_df.columns:
            final_df = final_df.sort_values(by='value', ascending=False)
        
        for _, row in final_df.iterrows():
            try:
                # 🚨 여기서 현재 주가(stock_service)를 쓸 수도 있지만, 일단은 저장용 구조체 생성
                holdings_list.append(Holding(
                    name_of_issuer=str(row.get('name_of_issuer', 'Unknown')),
                    cusip=str(row.get('cusip', '0000')),
                    ticker=str(row.get('cusip', '0000')), # 임시로 cusip 넣음
                    value=int(row.get('value', 0)),
                    shares=int(row.get('shares', 0)),
                    ssh_prnamt_type="SH",
                    change_rate=round(float(row.get('change_rate', 0.0)), 2),
                    prev_shares=int(row.get('prev_shares', 0)),
                    holding_type="Stock"
                ))
            except: continue
            
        return FilingResponse(
            cik=cik,
            institution_name=institution_name,
            report_date=target_filings[0]['date'],
            holdings=holdings_list
        )