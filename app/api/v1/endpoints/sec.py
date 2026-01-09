from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm

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
# 2. 대시보드 화면 API (🚀 AI 제거 -> 즉시 로딩)
# ==========================================
@router.get("/dashboard/{cik}")
async def get_dashboard(request: Request, cik: str, db: Session = Depends(get_db)):
    """
    사용자에게 보여지는 대시보드 화면입니다.
    DB 연결 방식을 Depends(get_db)로 통일하여 안정성을 높였습니다.
    """
    # 변수 초기화
    institution_name = ""
    report_date = ""
    display_holdings = []
    
    try:
        # 1. DB 먼저 확인 (Cache)
        saved_inst = db.query(Institution).filter(Institution.cik == cik).first()
        
        if saved_inst and saved_inst.holdings:
            print(f"✨ [DB Hit] {saved_inst.name} 데이터를 DB에서 가져옵니다.")
            institution_name = saved_inst.name
            # DB에 저장된 날짜가 있다면 그것을 쓰고, 없으면 기본값
            report_date = str(saved_inst.last_updated.date()) if hasattr(saved_inst, 'last_updated') and saved_inst.last_updated else "2025-09-30"
            
            # DB 모델 객체에서 데이터 추출
            for h in saved_inst.holdings:
                display_holdings.append({
                    "name_of_issuer": getattr(h, "name", getattr(h, "name_of_issuer", "Unknown")), # 안전장치
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
            
            # Pydantic 모델에서 데이터 추출
            for h in filing_data.holdings[:100]:
                h_dict = h.dict()
                h_dict['display_name'] = h.name_of_issuer # Pydantic은 name_of_issuer 사용
                h_dict['ticker'] = "" 
                display_holdings.append(h_dict)

        # 🚨 AI 분석 로직 제거됨 (기다리지 않고 바로 HTML 반환)
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": institution_name,
            "report_date": report_date,
            "holdings": display_holdings
        })
        
    except Exception as e:
        print(f"🔥 대시보드 에러 발생: {e}")
        # 에러가 나도 빈 화면이라도 보여주기 위해 템플릿 반환
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": "Error Loading Data",
            "report_date": "-",
            "holdings": []
        })

# ==========================================
# 3. 🤖 AI 분석 전용 API (Lazy Loading용)
# ==========================================
@router.get("/dashboard/{cik}/ai-analysis")
async def get_ai_analysis_endpoint(cik: str, db: Session = Depends(get_db)):
    """
    프론트엔드에서 비동기(JS)로 호출하는 AI 분석 API입니다.
    DB에 저장된 요약이 있으면 그걸 쓰고, 없으면 새로 생성 후 저장합니다.
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

        # 3. [분석 시작] DB에 없으면 AI 서비스 호출
        # 🚨 [수정 완료] 'name_of_issuer' 속성 에러 방지 코드 적용
        # DB 모델(Holding)에는 'name' 컬럼이 있고, SEC 데이터에는 'name_of_issuer'가 있을 수 있음
        # getattr(객체, '우선순위1', getattr(객체, '우선순위2', '기본값')) 패턴 사용
        holdings_list = []
        
        # 관계형 데이터(institution.holdings)가 로딩되어 있는지 확인
        source_holdings = institution.holdings
        
        # 만약 비어있으면 직접 쿼리 (안전장치)
        if not source_holdings:
             from app.models import Holding
             source_holdings = db.query(Holding).filter(Holding.institution_id == institution.id).limit(20).all()

        # 데이터 정제 (AI에게 보낼 포맷)
        for h in source_holdings:
            name = getattr(h, "name", getattr(h, "name_of_issuer", "Unknown"))
            holdings_list.append({"name_of_issuer": name, "value": h.value})

        # 4. AI 서비스 호출
        print(f"🚀 AI 분석 요청 시작: {institution.name}")
        analysis_result = await analyze_portfolio_by_llm(holdings_list, institution.name)

        # 5. 💾 [기억 저장] 결과가 정상적이면 DB에 저장!
        if "오류" not in analysis_result and len(analysis_result) > 30:
            institution.ai_summary = analysis_result
            db.commit() # 저장 확정
            print(f"💾 [Saved] 분석 결과를 DB에 저장했습니다.")

        return {"analysis": analysis_result}

    except Exception as e:
        print(f"🔥 AI 분석 엔드포인트 에러: {e}")
        return {"analysis": f"분석 중 오류가 발생했습니다. ({str(e)})"}