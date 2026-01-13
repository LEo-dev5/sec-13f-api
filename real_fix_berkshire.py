# real_fix_berkshire.py
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
try:
    from update_cache import update_stock_summary
except ImportError:
    update_stock_summary = None

# 🚨 [핵심 수정] SEC가 좋아하는 형식의 신분증(User-Agent)으로 변경
# 형식: 앱이름/버전 (이메일주소)
HEADERS = {
    "User-Agent": "Easy13F_Analyzer/2.0 (admin@easy13f.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov" 
}
# data.sec.gov용 헤더는 Host가 다를 수 있어서 분리
API_HEADERS = {
    "User-Agent": "Easy13F_Analyzer/2.0 (admin@easy13f.com)",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

def fix_berkshire_manual():
    print("🚑 [버크셔] 독립형 강제 복구 스크립트 (보안 강화판) 시작...")
    db = SessionLocal()
    CIK = "0001067983" 
    
    try:
        # 1. 기존 데이터 삭제
        inst = db.query(Institution).filter(Institution.cik == CIK).first()
        if inst:
            print("🧹 기존 데이터 청소 중...")
            db.execute(text(f"DELETE FROM holdings WHERE institution_id = {inst.id}"))
            db.commit()
        else:
            print("✨ 기관 정보 생성 중...")
            inst = Institution(cik=CIK, name="BERKSHIRE HATHAWAY INC", is_featured=True)
            db.add(inst)
            db.commit()
            db.refresh(inst)

        # 2. 최신 13F 보고서 찾기 (JSON API)
        print("🔍 [1단계] 최신 보고서(13F-HR) 찾는 중...")
        url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
        
        # 🚨 에러 확인 로직 추가
        resp = requests.get(url, headers=API_HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"🔥 [1단계 실패] 상태 코드: {resp.status_code}")
            print(f"내용: {resp.text[:200]}") # 에러 내용 일부 출력
            return
            
        data = resp.json()
        filings = data['filings']['recent']
        
        accession_num = None
        for i, form in enumerate(filings['form']):
            if form == '13F-HR':
                accession_num = filings['accessionNumber'][i]
                report_date = filings['reportDate'][i]
                print(f"📄 찾았다! 보고서 번호: {accession_num} (날짜: {report_date})")
                break
        
        if not accession_num:
            raise Exception("13F-HR 보고서를 찾을 수 없습니다.")

        # 3. XML 파일 주소 만들기
        # SEC는 요청을 너무 빨리 보내면 차단하므로 1초 쉼
        time.sleep(1) 
        
        clean_accession = accession_num.replace("-", "")
        index_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/index.json"
        
        print(f"🔍 [2단계] XML 주소 찾는 중... ({index_url})")
        idx_resp = requests.get(index_url, headers=HEADERS, timeout=30)
        
        # 🚨 여기서 에러나면 내용 출력
        if idx_resp.status_code != 200:
            print(f"🔥 [2단계 실패] 상태 코드: {idx_resp.status_code}")
            print(f"내용: {idx_resp.text[:300]}") # HTML 에러 메시지 확인
            return

        idx_data = idx_resp.json()
        
        xml_url = None
        for file in idx_data['directory']['item']:
            if file['name'].endswith('.xml') and ('info' in file['name'].lower() or 'table' in file['name'].lower()):
                xml_url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{clean_accession}/{file['name']}"
                print(f"🔗 발견된 XML: {xml_url}")
                break
        
        if not xml_url:
            raise Exception("XML 파일을 못 찾았습니다.")

        # 4. XML 다운로드 및 파싱
        print("📥 [3단계] 데이터 다운로드 및 분석 중...")
        time.sleep(1) # 또 1초 쉼 (차단 방지)
        
        xml_resp = requests.get(xml_url, headers=HEADERS, timeout=60)
        root = ET.fromstring(xml_resp.content)
        
        # 네임스페이스 처리
        ns_map = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
        
        holdings = []
        for info in root.findall('.//ns:infoTable', ns_map) if ns_map else root.findall('.//infoTable'):
            name_node = info.find('ns:nameOfIssuer', ns_map) if ns_map else info.find('nameOfIssuer')
            val_node = info.find('ns:value', ns_map) if ns_map else info.find('value')
            shrs_node = info.find('ns:shrsOrPrnAmt', ns_map) if ns_map else info.find('shrsOrPrnAmt')
            ssh_node = shrs_node.find('ns:sshPrnamt', ns_map) if ns_map else shrs_node.find('sshPrnamt')
            
            # 티커(CUSIP) 태그 찾기 시도
            cusip_node = info.find('ns:cusip', ns_map) if ns_map else info.find('cusip')

            name = name_node.text if name_node is not None else "Unknown"
            value = int(val_node.text) * 1000 if val_node is not None else 0
            shares = int(ssh_node.text) if ssh_node is not None else 0
            cusip = cusip_node.text if cusip_node is not None else ""

            if value > 0:
                # 간단하게 이름 첫 단어를 티커로 (나중에 DB 맵핑으로 보정됨)
                fake_ticker = name.split(" ")[0].replace(".", "").replace(",", "")
                
                holdings.append(Holding(
                    institution_id=inst.id,
                    name=name,
                    name_of_issuer=name,
                    ticker=fake_ticker, 
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
        
        total = db.execute(text(f"SELECT sum(value) FROM holdings WHERE institution_id = {inst.id}")).scalar()
        print(f"💰 [성공] 복구 완료! 총 자산: ${int(total):,}")
        
        # 6. 검색 장부 업데이트
        if update_stock_summary:
            print("📚 검색 장부 업데이트...")
            update_stock_summary()
            print("✅ 완료!")

    except Exception as e:
        print(f"🔥 스크립트 에러: {e}")
        db.rollback()