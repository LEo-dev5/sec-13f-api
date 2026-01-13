# real_fix_berkshire.py
import requests
import xml.etree.ElementTree as ET
import time
import sys
import os

# Render DB 연결 설정을 위해 경로 추가
sys.path.append(os.getcwd())
from sqlalchemy import text
from app.db.database import SessionLocal, engine
from app.db.models import Institution, Holding
from update_cache import update_stock_summary

# 🚨 SEC가 차단하지 못하도록 '진짜 사람처럼' 보이는 헤더 사용
HEADERS = {
    "User-Agent": "MyInvestmentResearch/1.0 (contact@research.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fix_berkshire_manual():
    print("🚑 [버크셔] 독립형 강제 복구 스크립트 시작...")
    db = SessionLocal()
    CIK = "0001067983" # 버크셔 CIK
    
    try:
        # 1. 기존 데이터 삭제
        print("🧹 기존 데이터 청소 중...")
        inst = db.query(Institution).filter(Institution.cik == CIK).first()
        if inst:
            db.execute(text(f"DELETE FROM holdings WHERE institution_id = {inst.id}"))
            db.commit()
            print("🗑️ 0달러 데이터 삭제 완료.")
        else:
            print("✨ 기관 정보가 없어서 새로 만듭니다.")
            inst = Institution(cik=CIK, name="BERKSHIRE HATHAWAY INC", is_featured=True)
            db.add(inst)
            db.commit()
            db.refresh(inst)

        # 2. 최신 13F 보고서 찾기 (JSON API)
        print("🔍 최신 보고서(13F-HR) 위치 찾는 중...")
        url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        
        if resp.status_code != 200:
            raise Exception(f"SEC 접속 실패: {resp.status_code}")
            
        data = resp.json()
        filings = data['filings']['recent']
        
        accession_num = None
        primary_doc = None
        
        for i, form in enumerate(filings['form']):
            if form == '13F-HR': # 13F-HR이 정기 보고서 (Amendment 아님)
                accession_num = filings['accessionNumber'][i]
                primary_doc = filings['primaryDocument'][i]
                report_date = filings['reportDate'][i]
                print(f"📄 찾았다! 보고서 번호: {accession_num} (날짜: {report_date})")
                break
        
        if not accession_num:
            raise Exception("13F-HR 보고서를 찾을 수 없습니다.")

        # 3. XML 파일 주소 만들기
        # SEC 주소 규칙: accessionNumber에서 '-' 제거한 폴더 안에 있음
        clean_accession = accession_num.replace("-", "")
        
        # 3-1. index.json에서 infoTable(보유종목표) XML 찾기
        index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/index.json"
        idx_resp = requests.get(index_url, headers=HEADERS, timeout=30)
        idx_data = idx_resp.json()
        
        xml_url = None
        for file in idx_data['directory']['item']:
            # 보통 xml 파일이고 이름에 'info'나 'table'이 들어감
            if file['name'].endswith('.xml') and ('info' in file['name'].lower() or 'table' in file['name'].lower()):
                xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/{file['name']}"
                print(f"🔗 보유 종목 XML 발견: {xml_url}")
                break
        
        if not xml_url:
            raise Exception("보유 종목 XML 파일(InfoTable)을 못 찾았습니다.")

        # 4. XML 다운로드 및 파싱
        print("📥 XML 데이터 다운로드 및 분석 중...")
        xml_resp = requests.get(xml_url, headers=HEADERS, timeout=60) # 타임아웃 60초
        xml_content = xml_resp.content
        
        root = ET.fromstring(xml_content)
        # 네임스페이스 제거 (파싱 쉽게 하기 위해)
        ns_map = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        
        holdings = []
        for info in root.findall('.//ns:infoTable', ns_map) if ns_map else root.findall('.//infoTable'):
            # 데이터 추출
            name_node = info.find('ns:nameOfIssuer', ns_map) if ns_map else info.find('nameOfIssuer')
            val_node = info.find('ns:value', ns_map) if ns_map else info.find('value')
            shrs_node = info.find('ns:shrsOrPrnAmt', ns_map) if ns_map else info.find('shrsOrPrnAmt')
            ssh_node = shrs_node.find('ns:sshPrnamt', ns_map) if ns_map else shrs_node.find('sshPrnamt')
            ticker_node = info.find('ns:cusip', ns_map) if ns_map else info.find('cusip') # 티커 대신 CUSIP 쓰는 경우가 많음

            name = name_node.text if name_node is not None else "Unknown"
            value = int(val_node.text) * 1000 if val_node is not None else 0 # 단위가 $1000임
            shares = int(ssh_node.text) if ssh_node is not None else 0
            cusip = ticker_node.text if ticker_node is not None else ""

            # 최소한의 데이터 유효성 검사
            if value > 0:
                holdings.append(Holding(
                    institution_id=inst.id,
                    name=name,
                    name_of_issuer=name,
                    ticker=name.split(" ")[0], # 임시로 이름 첫 단어를 티커로 (나중에 DB 맵핑으로 보정)
                    value=value,
                    shares=shares,
                    cusip=cusip,
                    holding_type="Stock"
                ))

        print(f"📦 추출된 종목 수: {len(holdings)}개")

        # 5. DB 저장
        print("💾 DB에 저장 중...")
        db.bulk_save_objects(holdings)
        db.commit()
        
        # 총 자산 확인
        total = db.execute(text(f"SELECT sum(value) FROM holdings WHERE institution_id = {inst.id}")).scalar()
        print(f"💰 [성공] 버크셔 총 자산 복구 완료: ${int(total):,}")
        
        # 6. 검색 장부 업데이트
        print("📚 검색 장부 최신화...")
        update_stock_summary()
        print("🎉 모든 작업 완료!")

    except Exception as e:
        print(f"🔥 실패 원인: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_berkshire_manual()