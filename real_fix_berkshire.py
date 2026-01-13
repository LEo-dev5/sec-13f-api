# real_fix_berkshire.py (메모리 최적화 버전)
import requests
import xml.etree.ElementTree as ET
import time
import sys
import os

# Render DB 연결 설정
sys.path.append(os.getcwd())
from sqlalchemy import text
from app.db.database import SessionLocal
from app.db.models import Institution, Holding

# SEC 차단 방지 헤더
HEADERS = {
    "User-Agent": "Easy13F_Analyzer/2.0 (admin@easy13f.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}
API_HEADERS = {
    "User-Agent": "Easy13F_Analyzer/2.0 (admin@easy13f.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fix_berkshire_manual():
    print("🚀 [Start] 버크셔 메모리 최적화 복구 시작!", flush=True)
    db = SessionLocal()
    CIK = "0001067983" 
    
    try:
        # 1. 기존 데이터 삭제
        inst = db.query(Institution).filter(Institution.cik == CIK).first()
        if inst:
            print("🧹 기존 데이터 삭제 중...", flush=True)
            db.execute(text(f"DELETE FROM holdings WHERE institution_id = {inst.id}"))
            db.commit()
        else:
            print("✨ 기관 생성 중...", flush=True)
            inst = Institution(cik=CIK, name="BERKSHIRE HATHAWAY INC", is_featured=True)
            db.add(inst)
            db.commit()
            db.refresh(inst)

        # 2. JSON에서 XML 주소 찾기
        print("🔍 보고서 위치 찾는 중...", flush=True)
        url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
        resp = requests.get(url, headers=API_HEADERS, timeout=30)
        
        data = resp.json()
        filings = data['filings']['recent']
        accession_num = None
        
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                accession_num = filings['accessionNumber'][i]
                break
        
        if not accession_num:
            print("❌ 보고서를 못 찾았습니다.")
            return

        time.sleep(1) # 차단 방지
        
        # XML 파일 찾기
        clean_accession = accession_num.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/index.json"
        
        idx_resp = requests.get(index_url, headers=HEADERS, timeout=30)
        idx_data = idx_resp.json()
        
        xml_url = None
        for file in idx_data['directory']['item']:
            if file['name'].endswith('.xml') and ('info' in file['name'].lower() or 'table' in file['name'].lower()):
                xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/{file['name']}"
                print(f"🔗 XML 발견: {xml_url}", flush=True)
                break

        # 3. 🚨 [핵심] 스트리밍 방식으로 다운로드 & 파싱 (메모리 절약)
        print("📥 스트리밍 다운로드 시작 (메모리 안전 모드)...", flush=True)
        
        # stream=True로 설정하여 한 번에 다 받지 않음
        with requests.get(xml_url, headers=HEADERS, stream=True) as r:
            r.raise_for_status()
            
            # iterparse로 조금씩 읽음
            context = ET.iterparse(r.raw, events=("end",))
            
            count = 0
            batch = []
            
            for event, elem in context:
                # 태그 이름에서 네임스페이스 제거 ({...}infoTable -> infoTable)
                tag = elem.tag.split("}")[-1]
                
                if tag == "infoTable":
                    # 데이터 추출
                    name_node = elem.find(".//nameOfIssuer")
                    if name_node is None: # 네임스페이스가 있는 경우 다시 시도
                        for child in elem:
                            if "nameOfIssuer" in child.tag: name_node = child
                            
                    # 값 찾기 (복잡한 XML 구조 대응)
                    name = "Unknown"
                    value = 0
                    shares = 0
                    
                    for child in elem.iter():
                        tag_name = child.tag.split("}")[-1]
                        if tag_name == "nameOfIssuer": name = child.text
                        elif tag_name == "value": value = int(child.text) * 1000
                        elif tag_name == "sshPrnamt": shares = int(child.text)
                    
                    if value > 0:
                        # 티커 가공
                        clean_ticker = name.split(" ")[0].replace(".", "").replace(",", "")
                        
                        batch.append(Holding(
                            institution_id=inst.id,
                            name=name,
                            name_of_issuer=name,
                            ticker=clean_ticker,
                            value=value,
                            shares=shares,
                            holding_type="Stock"
                        ))
                        count += 1

                    # 4. 500개씩 끊어서 저장 (DB 부하 방지)
                    if len(batch) >= 500:
                        db.bulk_save_objects(batch)
                        db.commit()
                        batch = [] # 비우기
                        print(f"✅ {count}개 처리 중...", flush=True)

                    # 🚨 메모리 해제 (가장 중요!)
                    elem.clear()
            
            # 남은 것 저장
            if batch:
                db.bulk_save_objects(batch)
                db.commit()

        print(f"🎉 최종 완료! 총 {count}개 종목 저장됨.", flush=True)
        
        # 총 자산 확인
        total = db.execute(text(f"SELECT sum(value) FROM holdings WHERE institution_id = {inst.id}")).scalar()
        print(f"💰 복구된 총 자산: ${int(total):,}")

    except Exception as e:
        print(f"🔥 에러: {e}", flush=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_berkshire_manual()