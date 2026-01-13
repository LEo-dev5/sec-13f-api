# real_fix_berkshire.py (SEC 차단 회피 및 디버깅 강화)
import requests
import xml.etree.ElementTree as ET
import time
import sys
import os

sys.path.append(os.getcwd())
from sqlalchemy import text
from app.db.database import SessionLocal
from app.db.models import Institution, Holding

# 🚨 [핵심] SEC는 브라우저 흉내보다 '이메일이 포함된 정직한 헤더'를 좋아합니다.
HEADERS = {
    "User-Agent": "InvestInsight_Bot/1.0 (kang203062@gmail.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}
API_HEADERS = {
    "User-Agent": "InvestInsight_Bot/1.0 (kang203062@gmail.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fix_berkshire_manual():
    print("🚀 [최후 수단] 버크셔 복구 시작...", flush=True)
    db = SessionLocal()
    CIK = "0001067983" 
    
    try:
        # 1. 기존 데이터 삭제
        inst = db.query(Institution).filter(Institution.cik == CIK).first()
        if inst:
            print("🧹 기존 데이터 청소...", flush=True)
            db.execute(text(f"DELETE FROM holdings WHERE institution_id = {inst.id}"))
            db.commit()
        else:
            print("✨ 기관 생성...", flush=True)
            inst = Institution(cik=CIK, name="BERKSHIRE HATHAWAY INC", is_featured=True)
            db.add(inst)
            db.commit()
            db.refresh(inst)

        # 2. JSON에서 최신 보고서 찾기
        print("🔍 보고서 위치 확인 중...", flush=True)
        url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
        
        # 1차 차단 확인
        resp = requests.get(url, headers=API_HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"🔥 SEC 접속 차단됨 (Code: {resp.status_code})")
            print("내용:", resp.text[:200])
            return

        data = resp.json()
        filings = data['filings']['recent']
        accession_num = None
        
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                accession_num = filings['accessionNumber'][i]
                print(f"📄 보고서 번호: {accession_num}", flush=True)
                break
        
        if not accession_num:
            print("❌ 보고서를 못 찾았습니다.")
            return

        time.sleep(2) # 차단 방지 대기
        
        # 3. XML 파일 찾기 (숫자 파일명 자동 인식)
        clean_accession = accession_num.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/index.json"
        
        idx_resp = requests.get(index_url, headers=HEADERS, timeout=30)
        if idx_resp.status_code != 200:
            print(f"❌ 파일 목록 접근 불가: {idx_resp.status_code}")
            return

        files = idx_resp.json()['directory']['item']
        target_file = None
        
        # XML 파일 중 가장 유력한 것 찾기
        xml_files = [f for f in files if f['name'].endswith('.xml')]
        print(f"📂 발견된 XML: {[f['name'] for f in xml_files]}", flush=True)

        for f in xml_files:
            fname = f['name']
            if 'info' in fname.lower() or 'table' in fname.lower():
                target_file = fname
                break
        
        # 없으면 primary_doc 제외하고 선택 (숫자 파일 선택)
        if not target_file:
            for f in xml_files:
                if 'primary' not in f['name'].lower():
                    target_file = f['name']
                    break
        
        if not target_file:
            print("❌ XML 데이터 파일을 찾을 수 없습니다.")
            return

        xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/{target_file}"
        print(f"🔗 다운로드 시도: {xml_url}", flush=True)

        # 4. 다운로드 및 내용 검증 (여기가 핵심)
        time.sleep(2)
        
        with requests.get(xml_url, headers=HEADERS, stream=True, timeout=60) as r:
            # HTML 차단 여부 확인 (Content-Type)
            ctype = r.headers.get('Content-Type', '').lower()
            if 'html' in ctype:
                print("\n🚨 [긴급] SEC가 다운로드를 차단했습니다 (HTML 반환됨).")
                print("--- 차단 메시지 ---")
                print(r.text[:300]) # 차단 메시지 출력
                print("-------------------")
                print("💡 해결책: Render 서버 IP가 일시 차단됨. 10분 뒤 실행하세요.")
                return

            print("📥 데이터 파싱 시작 (메모리 절약 모드)...", flush=True)
            
            try:
                context = ET.iterparse(r.raw, events=("end",))
                count = 0
                batch = []
                
                for event, elem in context:
                    tag = elem.tag.split("}")[-1]
                    if tag == "infoTable":
                        name = "Unknown"
                        value = 0
                        shares = 0
                        
                        for child in elem.iter():
                            ctag = child.tag.split("}")[-1]
                            if ctag == "nameOfIssuer": name = child.text
                            elif ctag == "value": 
                                try: value = int(child.text) * 1000
                                except: value = 0
                            elif ctag == "sshPrnamt":
                                try: shares = int(child.text)
                                except: shares = 0
                        
                        if value > 0:
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
                        
                        elem.clear()
                        
                        if len(batch) >= 1000:
                            db.bulk_save_objects(batch)
                            db.commit()
                            batch = []
                            print(f"✅ {count}개 저장...", flush=True)
                
                if batch:
                    db.bulk_save_objects(batch)
                    db.commit()
                    
            except ET.ParseError as e:
                print(f"\n🔥 [파싱 실패] 파일이 깨졌거나 XML이 아닙니다: {e}")
                return

        print(f"🎉 성공! 총 {count}개 종목 복구됨.", flush=True)
        
        # 총 자산 확인
        total = db.execute(text(f"SELECT sum(value) FROM holdings WHERE institution_id = {inst.id}")).scalar()
        print(f"💰 복구된 자산: ${int(total):,}")
        
        # 검색 장부 업데이트
        try:
            from update_cache import update_stock_summary
            print("📚 검색 장부 업데이트...", flush=True)
            update_stock_summary()
        except:
            pass

    except Exception as e:
        print(f"🔥 에러: {e}", flush=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_berkshire_manual()