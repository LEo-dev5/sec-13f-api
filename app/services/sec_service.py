import httpx
import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import asyncio
from app.schemas.stock import Holding, FilingResponse

# 🚨 [핵심 수정 1] 헤더 분리 전략
# SEC는 서버가 2개입니다. (data.sec.gov / www.sec.gov)
# 각각 맞는 Host 헤더를 보내지 않으면 봇으로 간주하고 차단합니다.

USER_AGENT = "Easy13F_Project (kang203062@gmail.com)"

# 1. 제출 정보 조회용 헤더 (data.sec.gov)
HEADERS_DATA = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

# 2. 문서 다운로드용 헤더 (www.sec.gov)
HEADERS_ARCHIVE = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}

# [안전장치] 빈 데이터프레임 컬럼 정의
EMPTY_COLUMNS = ['name_of_issuer', 'cusip', 'value', 'shares', 'ssh_prnamt_type', 'holding_type']

def get_empty_df():
    return pd.DataFrame(columns=EMPTY_COLUMNS)

# [Helper] XML 파서
def parse_13f_xml_to_dict(xml_content: str) -> list[dict]:
    holdings = []
    try:
        root = ET.fromstring(xml_content)
        # 네임스페이스 처리 (SEC XML은 종종 네임스페이스가 붙음)
        # {http://www.sec.gov/edgar/document/thirteenf/informationtable} 같은 거 무시하도록 처리
        for info in root.findall(".//{*}infoTable"):
            try:
                issuer_node = info.find("{*}nameOfIssuer")
                cusip_node = info.find("{*}cusip")
                value_node = info.find("{*}value")
                shrs_node = info.find("{*}shrsOrPrnAmt")
                
                if issuer_node is None or value_node is None: continue

                ssh_amt_node = shrs_node.find("{*}sshPrnamt") if shrs_node is not None else None
                ssh_type_node = shrs_node.find("{*}sshPrnamtType") if shrs_node is not None else None
                
                # Put/Call 태그 확인
                put_call_node = info.find("{*}putCall")
                holding_type = "Stock"
                if put_call_node is not None and put_call_node.text:
                    raw_type = put_call_node.text.strip().upper()
                    if "PUT" in raw_type: holding_type = "Put"
                    elif "CALL" in raw_type: holding_type = "Call"

                holdings.append({
                    "name_of_issuer": issuer_node.text if issuer_node is not None else "Unknown",
                    "cusip": cusip_node.text if cusip_node is not None else "000000000",
                    "value": int(value_node.text),
                    "shares": int(ssh_amt_node.text) if ssh_amt_node is not None else 0,
                    "ssh_prnamt_type": ssh_type_node.text if ssh_type_node is not None else "SH",
                    "holding_type": holding_type
                })
            except (AttributeError, ValueError): 
                continue
    except Exception as e:
        print(f"⚠️ XML 파싱 실패: {e}")
    return holdings

# [Helper] DataFrame 다운로드
async def fetch_holdings_df(client, cik_int, accession_number):
    try:
        acc_no_path = accession_number.replace("-", "")
        # SEC Archives는 www.sec.gov 입니다. -> HEADERS_ARCHIVE 사용
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_path}/index.json"
        
        # 1. 인덱스 파일 요청
        index_resp = await client.get(index_url, headers=HEADERS_ARCHIVE)
        
        if index_resp.status_code != 200:
            print(f"❌ [SEC 차단/오류] {index_url} -> Status: {index_resp.status_code}")
            return get_empty_df()
        
        directory_data = index_resp.json()
        target_xml = ""
        
        # XML 찾기 로직
        for item in directory_data['directory']['item']:
            name = item['name'].lower()
            if name.endswith(".xml") and "primary_doc" not in name and "cover" not in name:
                if "infotable" in name or int(item.get('size', 0)) > 1000:
                    target_xml = item['name']
                    if "infotable" in name: break
        
        if not target_xml: return get_empty_df()
        
        # 2. 실제 XML 다운로드
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_path}/{target_xml}"
        xml_resp = await client.get(xml_url, headers=HEADERS_ARCHIVE)
        
        if xml_resp.status_code != 200:
            print(f"❌ [XML 다운 실패] Status: {xml_resp.status_code}")
            return get_empty_df()

        raw_data = parse_13f_xml_to_dict(xml_resp.text)
        if not raw_data: 
            print(f"⚠️ XML은 받았으나 데이터가 0건입니다.")
            return get_empty_df()
        
        df = pd.DataFrame(raw_data)
        
        # 그룹화 (같은 종목 합치기)
        if not df.empty:
            df_grouped = df.groupby(['cusip', 'holding_type']).agg({
                'name_of_issuer': 'first',
                'value': 'sum',
                'shares': 'sum',
                'ssh_prnamt_type': 'first'
            }).reset_index()
            return df_grouped
        else:
            return get_empty_df()
        
    except Exception as e:
        print(f"⚠️ DF 생성 에러: {e}")
        return get_empty_df()

# [Helper] 전체 명단 (Master Index)
async def fetch_all_13f_ciks(year: int, quarter: int) -> list[str]:
    print(f"📥 {year}년 {quarter}분기 Master Index 다운로드...")
    # Archives는 www.sec.gov 사용
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        resp = await client.get(url, headers=HEADERS_ARCHIVE)
        
        if resp.status_code != 200: 
            print(f"❌ Master Index 다운 실패: {resp.status_code}")
            return []

        lines = resp.text.splitlines()
        ciks = set()
        
        start_idx = 0
        for i, line in enumerate(lines):
            if "CIK|Company Name" in line:
                start_idx = i + 2
                break
        
        for line in lines[start_idx:]:
            parts = line.split('|')
            if len(parts) < 5: continue
            if parts[2] == '13F-HR':
                ciks.add(parts[0])
                
    print(f"✅ 총 {len(ciks)}개의 13F 제출 기관 발견!")
    return list(ciks)

# [Main] 최신 13F 가져오기
async def fetch_latest_13f(cik: str) -> FilingResponse:
    cik_int = str(int(cik))
    cik_padded = cik.zfill(10)
    
    # Submissions는 data.sec.gov 사용 -> HEADERS_DATA 사용
    submission_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        # 🚨 [수정] HEADERS_DATA 사용
        resp = await client.get(submission_url, headers=HEADERS_DATA)
        
        # 429 에러 처리 (재시도 로직)
        if resp.status_code == 429:
            print(f"⚠️ [Rate Limit] SEC 과부하. 2초 대기 후 재시도... ({cik})")
            await asyncio.sleep(2)
            resp = await client.get(submission_url, headers=HEADERS_DATA)

        if resp.status_code != 200: 
            print(f"❌ [Submission 실패] CIK:{cik} Status:{resp.status_code}")
            raise Exception(f"SEC 접속 에러: {resp.status_code}")
        
        data = resp.json()
        institution_name = data.get('name', 'Unknown').title()
        
        filings = data['filings']['recent']
        target_filings = []
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                target_filings.append({
                    'date': filings['reportDate'][i],
                    'acc': filings['accessionNumber'][i]
                })
                if len(target_filings) == 2: break
        
        if not target_filings: raise Exception("13F 보고서가 없습니다.")

        # 데이터 수집 (Archives 접근 -> 함수 내부에서 HEADERS_ARCHIVE 사용)
        df_curr = await fetch_holdings_df(client, cik_int, target_filings[0]['acc'])
        
        df_prev = pd.DataFrame()
        if len(target_filings) > 1:
            df_prev = await fetch_holdings_df(client, cik_int, target_filings[1]['acc'])

        final_df = df_curr.copy()
        if final_df.empty: final_df = get_empty_df()

        if 'change_rate' not in final_df.columns: final_df['change_rate'] = 0.0
        if 'prev_shares' not in final_df.columns: final_df['prev_shares'] = 0

        # Merge 로직
        if not df_prev.empty and not final_df.empty:
            try:
                merged = pd.merge(
                    df_curr, 
                    df_prev[['cusip', 'holding_type', 'shares']], 
                    on=['cusip', 'holding_type'],
                    how='left', 
                    suffixes=('', '_prev')
                )
                merged['prev_shares'] = merged['shares_prev'].fillna(0).astype(int)
                merged['change_rate'] = np.where(
                    merged['prev_shares'] > 0,
                    ((merged['shares'] - merged['prev_shares']) / merged['prev_shares'] * 100),
                    100.0
                )
                merged['change_rate'] = merged['change_rate'].replace([np.inf, -np.inf], 100.0)
                final_df = merged
            except Exception: pass

        holdings_list = []
        if 'value' in final_df.columns and not final_df.empty:
            final_df = final_df.sort_values(by='value', ascending=False)
        
        for _, row in final_df.iterrows():
            try:
                holdings_list.append(Holding(
                    name_of_issuer=str(row.get('name_of_issuer', 'Unknown')),
                    cusip=str(row.get('cusip', '0000')),
                    value=int(row.get('value', 0)),
                    shares=int(row.get('shares', 0)),
                    ssh_prnamt_type=str(row.get('ssh_prnamt_type', 'SH')),
                    change_rate=round(float(row.get('change_rate', 0.0)), 2),
                    prev_shares=int(row.get('prev_shares', 0)),
                    holding_type=str(row.get('holding_type', 'Stock'))
                ))
            except Exception: continue
            
        return FilingResponse(
            cik=cik,
            institution_name=institution_name,
            report_date=target_filings[0]['date'],
            holdings=holdings_list
        )