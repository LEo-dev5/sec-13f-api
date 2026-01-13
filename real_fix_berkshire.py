# real_fix_berkshire.py (최종_오류수정_방탄버전.py)
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
    "User-Agent": "Easy13F_Analyzer/3.0 (admin@easy13f.com)", # 버전 올림
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}
API_HEADERS = {
    "User-Agent": "Easy13F_Analyzer/3.0 (admin@easy13f.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fix_berkshire_manual():
    print("🚀 [Start] 버크셔 데이터 복구 (최종 수정판)...", flush=True)
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

        # 2. JSON에서 최신 보고서 찾기
        print("🔍 보고서 목록 조회 중...", flush=True)
        url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
        resp = requests.get(url, headers=API_HEADERS, timeout=30)
        
        if resp.status_code != 200:
            print(f"❌ SEC 접속 실패 (Status: {resp.status_code})")
            return

        data = resp.json()
        filings = data['filings']['recent']
        accession_num = None
        
        # 13F-HR 찾기
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                accession_num = filings['accessionNumber'][i]
                print(f"📄 최신 보고서 발견: {accession_num} ({filings['reportDate'][i]})", flush=True)
                break
        
        if not accession_num:
            print("❌ 13F-HR 보고서를 찾을 수 없습니다.")
            return

        time.sleep(1) 
        
        # 3. 파일 목록(index.json) 조회
        clean_accession = accession_num.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/index.json"
        
        idx_resp = requests.get(index_url, headers=HEADERS, timeout=30)
        if idx_resp.status_code != 200:
            print(f"❌ 파일 목록 조회 실패: {idx_resp.status_code}")
            return

        idx_data = idx_resp.json()
        files = idx_data['directory']['item']
        
        # 4. XML 파일 찾기 로직 (에러 방지 추가)
        target_file = None
        xml_candidates = []

        print("📂 파일 목록 분석 중...", flush=True)
        for file in files:
            fname = file['name']
            
            # 🚨 [수정] 사이즈가 없거나 빈 문자열이면 0으로 처리 (에러 원인 해결)
            size_str = file.get('size', '0')
            if size_str == '':
                size = 0
            else:
                try:
                    size = int(size_str)
                except ValueError:
                    size = 0
            
            # XML 파일만 수집
            if fname.endswith('.xml'):
                xml_candidates.append({'name': fname, 'size': size})
                
                # 우선순위: 이름에 info나 table이 들어간 것
                if 'info' in fname.lower() or 'table' in fname.lower():
                    target_file = fname
                    break
        
        # 못 찾았으면 가장 큰 파일 선택
        if not target_file and xml_candidates:
            print("⚠️ 이름으로 못 찾아서 가장 큰 XML 파일을 선택합니다.", flush=True)
            xml_candidates.sort(key=lambda x: x['size'], reverse=True)
            target_file = xml_candidates[0]['name']

        if not target_file:
            print("❌ XML 파일을 아예 찾을 수 없습니다.")
            return

        # 최종 URL 확정
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/{target_file}"
        print(f"🔗 다운로드 경로: {xml_url}", flush=True)

        # 5. 스트리밍 다운로드
        print("📥 데이터 다운로드 및 파싱 시작...", flush=True)
        
        count = 0
        batch = []
        
        with requests.get(xml_url, headers=HEADERS, stream=True) as r:
            r.raise_for_status()
            context = ET.iterparse(r.raw, events=("end",))
            
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
                            # 값도 빈칸일 수 있으니 방어
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
                        
                    elem.clear() # 메모리 해제
                    
                    if len(batch) >= 500:
                        db.bulk_save_objects(batch)
                        db.commit()
                        batch = []
                        print(f"✅ {count}개 저장 중...", flush=True)

            if batch:
                db.bulk_save_objects(batch)
                db.commit()

        print(f"🎉 최종 완료! 총 {count}개 종목 복구됨.", flush=True)
        
        # 총 자산 확인
        total = db.execute(text(f"SELECT sum(value) FROM holdings WHERE institution_id = {inst.id}")).scalar()
        print(f"💰 현재 버크셔 총 자산: ${int(total):,}")
        
        # 검색 장부 자동 업데이트
        try:
            from update_cache import update_stock_summary
            print("📚 검색 장부 업데이트 중...", flush=True)
            update_stock_summary()
            print("✅ 검색 기능까지 완료!")
        except:
            print("⚠️ 검색 장부 업데이트는 수동으로 해주세요.")

    except Exception as e:
        print(f"🔥 에러 발생: {e}", flush=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_berkshire_manual()