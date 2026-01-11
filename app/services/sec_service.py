import httpx
import pandas as pd
import xml.etree.ElementTree as ET
import numpy as np
import asyncio
import random
from app.schemas.stock import Holding, FilingResponse

# 🚨 [핵심 전략] User-Agent를 최대한 정중하게, 그리고 랜덤 딜레이를 위한 준비
USER_AGENT = "Easy13F_Project (kang203062@gmail.com)"

HEADERS_DATA = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

HEADERS_ARCHIVE = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}

EMPTY_COLUMNS = ['name_of_issuer', 'cusip', 'value', 'shares', 'ssh_prnamt_type', 'holding_type']

def get_empty_df():
    return pd.DataFrame(columns=EMPTY_COLUMNS)

def parse_13f_xml_to_dict(xml_content: str) -> list[dict]:
    holdings = []
    try:
        root = ET.fromstring(xml_content)
        for info in root.findall(".//{*}infoTable"):
            try:
                issuer_node = info.find("{*}nameOfIssuer")
                cusip_node = info.find("{*}cusip")
                value_node = info.find("{*}value")
                shrs_node = info.find("{*}shrsOrPrnAmt")
                
                if issuer_node is None or value_node is None: continue

                ssh_amt_node = shrs_node.find("{*}sshPrnamt") if shrs_node is not None else None
                ssh_type_node = shrs_node.find("{*}sshPrnamtType") if shrs_node is not None else None
                
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

async def fetch_holdings_df(client, cik_int, accession_number):
    try:
        acc_no_path = accession_number.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_path}/index.json"
        
        # 🚨 [Archives 요청] 여기서도 재시도 로직 적용
        index_resp = None
        for attempt in range(3):
            index_resp = await client.get(index_url, headers=HEADERS_ARCHIVE)
            if index_resp.status_code == 429:
                wait_time = 5 + (attempt * 5) + random.uniform(1, 3) # 6초, 11초, 16초... 점점 길게
                print(f"💤 [Archives 429] {wait_time:.1f}초 휴식 후 재시도...")
                await asyncio.sleep(wait_time)
                continue
            break
        
        if not index_resp or index_resp.status_code != 200:
            return get_empty_df()
        
        directory_data = index_resp.json()
        target_xml = ""
        
        for item in directory_data['directory']['item']:
            name = item['name'].lower()
            if name.endswith(".xml") and "primary_doc" not in name and "cover" not in name:
                if "infotable" in name or int(item.get('size', 0)) > 1000:
                    target_xml = item['name']
                    if "infotable" in name: break
        
        if not target_xml: return get_empty_df()
        
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no_path}/{target_xml}"
        xml_resp = await client.get(xml_url, headers=HEADERS_ARCHIVE)
        
        if xml_resp.status_code != 200:
            return get_empty_df()

        raw_data = parse_13f_xml_to_dict(xml_resp.text)
        if not raw_data: return get_empty_df()
        
        df = pd.DataFrame(raw_data)
        
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

async def fetch_all_13f_ciks(year: int, quarter: int) -> list[str]:
    # (이 부분은 동일하므로 생략 - 기존 코드 유지하거나 필요 시 복사)
    return []

# [Main] 최신 13F 가져오기
async def fetch_latest_13f(cik: str) -> FilingResponse:
    cik_int = str(int(cik))
    cik_padded = cik.zfill(10)
    submission_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        
        # 🚨 [핵심 수정] 강력한 재시도(Retry) 로직
        resp = None
        for attempt in range(4): # 총 4번 시도 (0, 1, 2, 3)
            try:
                resp = await client.get(submission_url, headers=HEADERS_DATA)
                
                if resp.status_code == 200:
                    break # 성공하면 탈출!
                
                if resp.status_code == 429:
                    # 429 뜨면 점점 더 오래 쉽니다 (5초 -> 10초 -> 15초)
                    # 랜덤 시간을 섞어서 기계가 아닌 척 합니다.
                    wait_time = 5 + (attempt * 5) + random.uniform(1, 4)
                    print(f"🔥 [SEC 과부하] {cik} - {attempt+1}차 시도 실패. {wait_time:.1f}초 동안 숨 고르기...")
                    await asyncio.sleep(wait_time)
                else:
                    # 429 말고 다른 에러면 그냥 중단
                    break
            except Exception as e:
                print(f"통신 오류: {e}")
                await asyncio.sleep(5)

        if not resp or resp.status_code != 200: 
            # 4번 다 실패하면 어쩔 수 없이 에러 처리
            status = resp.status_code if resp else "Connection Error"
            print(f"❌ [최종 실패] {cik} 데이터를 가져올 수 없습니다. (Status: {status})")
            raise Exception(f"SEC 접속 불가 (잠시 후 다시 시도해주세요)")
        
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

        # 여기 사이에도 딜레이를 줍니다
        await asyncio.sleep(random.uniform(1, 2))

        df_curr = await fetch_holdings_df(client, cik_int, target_filings[0]['acc'])
        
        await asyncio.sleep(random.uniform(1, 2)) # 딜레이

        df_prev = pd.DataFrame()
        if len(target_filings) > 1:
            df_prev = await fetch_holdings_df(client, cik_int, target_filings[1]['acc'])

        final_df = df_curr.copy()
        if final_df.empty: final_df = get_empty_df()

        if 'change_rate' not in final_df.columns: final_df['change_rate'] = 0.0
        if 'prev_shares' not in final_df.columns: final_df['prev_shares'] = 0

        # Merge Logic
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