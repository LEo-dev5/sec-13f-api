from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm
from app.services.wiki_service import get_company_description # 👈 [추가] 위키 서비스 임포트
from app.services.ai_service import analyze_portfolio_by_llm, translate_wiki_to_korean 
from app.services.wiki_service import get_company_description

router = APIRouter()

# 템플릿 폴더 위치 지정
templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 1. JSON API (앱 연동용 / 디버깅용)
# ==========================================
@router.get("/analysis/{cik}")
async def get_ai_analysis_json(cik: str):
    try:
        filing_data = await fetch_latest_13f(cik)
        
        analysis_result = await analyze_portfolio_by_llm(
            filing_data.holdings, 
            filing_data.institution_name 
        )
        
        return {
            "cik": cik,
            "institution": filing_data.institution_name,
            "report_date": filing_data.report_date,
            "top_holdings": filing_data.holdings[:5], 
            "ai_analysis": analysis_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. 대시보드 화면 API (🚀 위키백과 즉시 로딩 적용)
# ==========================================
@router.get("/dashboard/{cik}")
async def get_dashboard(request: Request, cik: str, db: Session = Depends(get_db)):
    """
    사용자에게 보여지는 대시보드 화면입니다.
    회사 개요(Description)는 위키백과에서 즉시 가져오고, 변동사항 분석은 AI가 Lazy Loading 합니다.
    """
    # 변수 초기화
    institution_name = ""
    report_date = ""
    description_text = "" # 👈 화면에 보여줄 설명
    display_holdings = []
    
    try:
        saved_inst = db.query(Institution).filter(Institution.cik == cik).first()
        
        if saved_inst:
            print(f"✨ [DB Hit] {cik} 데이터 로딩 중...")
            
            # 🚨🚨 [여기부터 수정] 이름이 없을 때 자동 복구하는 핵심 코드 🚨🚨
            if not saved_inst.name or saved_inst.name.strip() == "":
                print(f"⚠️ 경고: {cik}의 이름이 DB에 없습니다. SEC에서 긴급 복구합니다.")
                try:
                    # SEC 서버에서 다시 이름표 떼오기
                    fresh_data = await fetch_latest_13f(cik)
                    saved_inst.name = fresh_data.institution_name
                    db.commit() # DB에 이름 저장
                    db.refresh(saved_inst)
                    print(f"✅ 복구 완료: {saved_inst.name}")
                except Exception as e:
                    print(f"❌ 복구 실패: {e}")
                    # 실패하면 임시 이름이라도 부여
                    saved_inst.name = f"Institution ({cik})"

            # 이제 무조건 이름이 존재함
            institution_name = saved_inst.name
            # -----------------------------------------------

            # 날짜 처리
            report_date = str(saved_inst.last_updated.date()) if hasattr(saved_inst, 'last_updated') and saved_inst.last_updated else "2025-09-30"
            
            # 보유 종목 데이터 추출 (안전장치 적용)
            if saved_inst.holdings:
                for h in saved_inst.holdings:
                    display_holdings.append({
                        "name_of_issuer": getattr(h, "name", getattr(h, "name_of_issuer", "Unknown")),
                        "display_name": getattr(h, "name", getattr(h, "name_of_issuer", "Unknown")),
                        "ticker": h.ticker,
                        "value": h.value,
                        "shares": h.shares,
                        "change_rate": h.change_rate,
                        "holding_type": h.holding_type,
                    })
        else:
            # 2. DB에 없으면 SEC 웹 크롤링
            print(f"🌐 [SEC Web] {cik} 데이터를 SEC에서 다운로드합니다...")
            filing_data = await fetch_latest_13f(cik)
            
            institution_name = filing_data.institution_name
            report_date = filing_data.report_date

            # 온 김에 위키 검색도 같이 해서 보여줌 (저장은 다음 조회 때 DB 로직에서 처리됨)
            description_text = get_company_description(institution_name)
            
            # 데이터 추출
            for h in filing_data.holdings[:100]:
                h_dict = h.dict()
                h_dict['display_name'] = h.name_of_issuer
                h_dict['ticker'] = "" 
                display_holdings.append(h_dict)

        # 🚨 HTML 렌더링 (description 포함)
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": institution_name,
            "report_date": report_date,
            "holdings": display_holdings,
            "description": description_text # 👈 HTML로 전달
        })
        
    except Exception as e:
        print(f"🔥 대시보드 에러 발생: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": "Error Loading Data",
            "report_date": "-",
            "holdings": [],
            "description": ""
        })

# ==========================================
# 3. 🤖 AI 분석 전용 API (Lazy Loading용)
# ==========================================
@router.get("/dashboard/{cik}/ai-analysis")
async def get_ai_analysis_endpoint(cik: str, db: Session = Depends(get_db)):
    """
    AI 분석 결과를 반환합니다. (DB 캐싱 적용)
    """
    try:
        # 1. 기관 찾기
        institution = db.query(Institution).filter(Institution.cik == cik).first()
        if not institution:
            return {"analysis": "기관 정보를 찾을 수 없습니다. (먼저 대시보드를 로딩해주세요)"}

        # 2. 🧠 [기억력 발동] 이미 분석한 적이 있는지 확인
        if institution.ai_summary:
            print(f"✨ [Cache Hit] DB에서 저장된 분석글을 가져옵니다. ({institution.name})")
            return {"analysis": institution.ai_summary}

        # 3. [분석 시작] 데이터 준비
        holdings_list = []
        source_holdings = institution.holdings
        
        # 만약 비어있으면 직접 쿼리 (안전장치)
        if not source_holdings:
             from app.models import Holding
             source_holdings = db.query(Holding).filter(Holding.institution_id == institution.id).limit(20).all()

        for h in source_holdings:
            name = getattr(h, "name", getattr(h, "name_of_issuer", "Unknown"))
            # change_rate가 None이면 0으로 처리
            change = h.change_rate if h.change_rate is not None else 0 
            
            holdings_list.append({
                "name_of_issuer": name, 
                "value": h.value,
                "change_rate": change # 👈 핵심 정보 추가!
            })

        # 데이터 정제 (AI에게 보낼 포맷)
        for h in source_holdings:
            name = getattr(h, "name", getattr(h, "name_of_issuer", "Unknown"))
            holdings_list.append({"name_of_issuer": name, "value": h.value})

        # 4. AI 서비스 호출
        print(f"🚀 AI 분석 요청 시작: {institution.name}")
        analysis_result = await analyze_portfolio_by_llm(holdings_list, institution.name)

        # 5. 💾 [기억 저장] DB 저장
        if "오류" not in analysis_result and len(analysis_result) > 30:
            institution.ai_summary = analysis_result
            db.commit() # 저장 확정
            print(f"💾 [Saved] 분석 결과를 DB에 저장했습니다.")

        return {"analysis": analysis_result}

    except Exception as e:
        print(f"🔥 AI 분석 엔드포인트 에러: {e}")
        return {"analysis": f"분석 중 오류가 발생했습니다. ({str(e)})"}