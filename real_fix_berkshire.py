# real_fix_berkshire.py (파일 타입 기반 탐색 + 디버깅 모드)
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

# SEC 차단 방지 헤더 (더욱 사람처럼 보이게 수정)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (admin@easy13f.com)",
    "Accept": "application/xml,application/xhtml+xml,text/html;q=0.9,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov"
}
API_HEADERS = {
    "User-Agent": "Easy13F_Analyzer/4.0 (admin@easy13f.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fix_berkshire_manual():
    print("🚀 [Start] 버크셔 데이터 복구 (정밀 탐색 모드)...", flush=True)
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
        
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                accession_num = filings['accessionNumber'][i]
                print(f"📄 최신 보고서 발견: {accession_num} ({filings['reportDate'][i]})", flush=True)
                break
        
        if not accession_num:
            print("❌ 13F-HR 보고서를 찾을 수 없습니다.")
            return

        time.sleep(2) # 2초 대기 (차단 방지)
        
        # 3. 파일 목록(index.json) 조회
        clean_accession = accession_num.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/index.json"
        
        idx_resp = requests.get(index_url, headers=HEADERS, timeout=30)
        if idx_resp.status_code != 200:
            print(f"❌ 파일 목록 조회 실패: {idx_resp.status_code}")
            return

        idx_data = idx_resp.json()
        files = idx_data['directory']['item']
        
        # 4. XML 파일 찾기 (Type 기반 탐색)
        target_file = None
        
        print("📂 파일 목록 분석 중 (Type 확인)...", flush=True)
        for file in files:
            fname = file['name']
            ftype = file.get('type', '').upper()
            
            # 디버깅용 출력
            # print(f" - 파일: {fname} / 타입: {ftype}")

            # 'INFORMATION TABLE' 이라고 명시된 XML을 찾음 (가장 정확함)
            if 'INFORMATION TABLE' in ftype and fname.endswith('.xml'):
                target_file = fname
                print(f"🎯 정확한 데이터 파일 발견! ({fname})", flush=True)
                break
        
        # 만약 타입으로 못 찾으면, 이름에 'info'가 들어간 XML 찾기
        if not target_file:
            print("⚠️ 타입으로 못 찾음. 이름으로 재검색...", flush=True)
            for file in files:
                if file['name'].endswith('.xml') and ('info' in file['name'].lower()):
                    target_file = file['name']
                    print(f"🎯 이름으로 발견: {target_file}", flush=True)
                    break
        
        if not target_file:
            print("❌ [실패] 데이터 파일(XML)을 식별할 수 없습니다.")
            print(f"📄 전체 파일 목록: {[f['name'] for f in files]}")
            return

        # 최종 URL
        xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/{target_file}"
        print(f"🔗 다운로드 경로: {xml_url}", flush=True)

        # 5. 데이터 다운로드 및 내용 검증 (여기서 에러 잡음)
        print("📥 데이터 다운로드 중...", flush=True)
        time.sleep(1)
        
        # 먼저 내용을 살짝 봅니다.
        r = requests.get(xml_url, headers=HEADERS, timeout=60)
        content_preview = r.text[:500] # 앞부분 500자만 읽기
        
        # 만약 HTML 에러 페이지라면?
        if "<html" in content_preview.lower() or "<!doctype html" in content_preview.lower():
            print("\n🚨 [차단됨] SEC가 XML 대신 HTML 에러 페이지를 보냈습니다!")
            print(f"❌ 내용 미리보기:\n{content_preview}...")
            print("💡 해결책: 5분 정도 쉬었다가 다시 실행하세요.")
            return

        # XML 파싱 시작 (메모리 방식 사용 - 내용 검증됨)
        # 스트리밍 대신 바로 파싱 (위에서 이미 받았으므로)
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as e:
            print(f"\n🔥 [파싱 에러] XML 형식이 아닙니다: {e}")
            print(f"❌ 받은 데이터 앞부분:\n{content_preview}...")
            return

        print("✅ XML 유효성 확인 완료. 데이터 추출 시작...", flush=True)
        
        holdings = []
        # 네임스페이스 처리
        ns_map = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        
        for info in root.findall('.//ns:infoTable', ns_map) if ns_map else root.findall('.//infoTable'):
            name = "Unknown"
            value = 0
            shares = 0
            
            # 안전하게 태그 찾기
            def get_text(elem, tag_name):
                node = elem.find(f"ns:{tag_name}", ns_map) if ns_map else elem.find(tag_name)
                return node.text if node is not None else None

            name = get_text(info, 'nameOfIssuer') or "Unknown"
            
            val_text = get_text(info, 'value')
            if val_text: value = int(val_text) * 1000
            
            shrs_node = info.find('ns:shrsOrPrnAmt', ns_map) if ns_map else info.find('shrsOrPrnAmt')
            if shrs_node is not None:
                ssh_text = get_text(shrs_node, 'sshPrnamt')
                if ssh_text: shares = int(ssh_text)

            if value > 0:
                clean_ticker = name.split(" ")[0].replace(".", "").replace(",", "")
                holdings.append(Holding(
                    institution_id=inst.id,
                    name=name,
                    name_of_issuer=name,
                    ticker=clean_ticker,
                    value=value,
                    shares=shares,
                    holding_type="Stock"
                ))

        # DB 저장
        print(f"📦 추출된 종목 수: {len(holdings)}개. DB 저장 중...", flush=True)
        
        # 1000개씩 나눠서 저장
        batch_size = 1000
        for i in range(0, len(holdings), batch_size):
            batch = holdings[i:i + batch_size]
            db.bulk_save_objects(batch)
            db.commit()
            print(f" - {i + len(batch)}개 저장 완료...", flush=True)
            
        # 총 자산 확인
        total = db.execute(text(f"SELECT sum(value) FROM holdings WHERE institution_id = {inst.id}")).scalar()
        print(f"💰 [복구 성공] 버크셔 총 자산: ${int(total):,}")
        
        # 검색 장부 자동 업데이트
        try:
            from update_cache import update_stock_summary
            print("📚 검색 장부 업데이트 중...", flush=True)
            update_stock_summary()
            print("✅ 검색 기능까지 완료!")
        except:
            pass

    except Exception as e:
        print(f"🔥 시스템 에러: {e}", flush=True)
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_berkshire_manual()