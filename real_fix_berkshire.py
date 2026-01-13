# real_fix_berkshire.py (숫자 파일명 자동 인식 버전)
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

# 차단 방지용 헤더
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (admin@easy13f.com)",
    "Accept": "application/xml,application/xhtml+xml,text/xml,text/html;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}
API_HEADERS = {
    "User-Agent": "Easy13F_Analyzer/5.0 (admin@easy13f.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fix_berkshire_manual():
    print("🚀 [Start] 버크셔 데이터 복구 (파일명 대응 패치)...", flush=True)
    db = SessionLocal()
    CIK = "0001067983" 
    
    try:
        # 1. 기존 데이터 삭제
        inst = db.query(Institution).filter(Institution.cik == CIK).first()
        if inst:
            print("🧹 기존 데이터 청소 중...", flush=True)
            db.execute(text(f"DELETE FROM holdings WHERE institution_id = {inst.id}"))
            db.commit()
        else:
            print("✨ 기관 생성 중...", flush=True)
            inst = Institution(cik=CIK, name="BERKSHIRE HATHAWAY INC", is_featured=True)
            db.add(inst)
            db.commit()
            db.refresh(inst)

        # 2. 최신 보고서 찾기
        print("🔍 보고서 목록 조회 중...", flush=True)
        url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
        resp = requests.get(url, headers=API_HEADERS, timeout=30)
        
        if resp.status_code != 200:
            print(f"❌ SEC API 접속 실패: {resp.status_code}")
            return

        data = resp.json()
        filings = data['filings']['recent']
        accession_num = None
        
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                accession_num = filings['accessionNumber'][i]
                print(f"📄 최신 보고서: {accession_num} ({filings['reportDate'][i]})", flush=True)
                break
        
        if not accession_num:
            print("❌ 13F-HR 보고서를 찾을 수 없습니다.")
            return

        time.sleep(1)
        
        # 3. 파일 목록 조회
        clean_accession = accession_num.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/index.json"
        
        idx_resp = requests.get(index_url, headers=HEADERS, timeout=30)
        files = idx_resp.json()['directory']['item']
        
        # 4. XML 파일 선택 로직 (개선됨)
        target_file = None
        xml_files = [f for f in files if f['name'].endswith('.xml')]
        
        print(f"📂 발견된 XML 파일들: {[f['name'] for f in xml_files]}", flush=True)

        for f in xml_files:
            fname = f['name']
            # 1순위: 이름에 info, table이 들어간 것
            if 'info' in fname.lower() or 'table' in fname.lower():
                target_file = fname
                break
        
        # 2순위: 못 찾았다면 'primary_doc.xml'(표지)이 아닌 다른 XML을 선택
        if not target_file:
            for f in xml_files:
                if 'primary' not in f['name'].lower():
                    target_file = f['name']
                    print(f"👉 숫자/임의 이름 파일 선택됨: {target_file}", flush=True)
                    break

        if not target_file:
            print("❌ 적절한 데이터 파일을 찾을 수 없습니다.")
            return

        # URL 확정
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/{target_file}"
        print(f"🔗 다운로드 시작: {xml_url}", flush=True)

        # 5. 데이터 다운로드 및 파싱
        # 차단 방지를 위해 잠시 대기
        time.sleep(2)
        
        with requests.get(xml_url, headers=HEADERS, stream=True, timeout=60) as r:
            # 상태 코드 체크
            if r.status_code != 200:
                print(f"🔥 다운로드 실패 (Status: {r.status_code})")
                print("내용:", r.text[:200])
                return

            # 내용이 HTML인지 체크 (Content-Type 헤더 확인)
            ctype = r.headers.get('Content-Type', '').lower()
            if 'html' in ctype:
                print("🚨 [차단됨] XML 대신 HTML 페이지가 반환되었습니다.")
                print("내용 미리보기:", r.text[:300])
                return

            # 파싱 시작
            print("📥 데이터 처리 중 (스트리밍)...", flush=True)
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
                            print(f"✅ {count}개 저장 중...", flush=True)
                
                if batch:
                    db.bulk_save_objects(batch)
                    db.commit()

            except ET.ParseError as e:
                print(f"🔥 파싱 에러 (파일이 깨졌거나 HTML임): {e}")
                return

        print(f"🎉 최종 복구 완료! 총 {count}개 종목.", flush=True)
        
        # 총 자산 확인
        total = db.execute(text(f"SELECT sum(value) FROM holdings WHERE institution_id = {inst.id}")).scalar()
        print(f"💰 현재 버크셔 총 자산: ${int(total):,}")
        
        # 캐시 업데이트
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