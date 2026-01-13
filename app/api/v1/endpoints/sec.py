from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.db.database import get_db
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm 
from app.services.wiki_service import get_company_description 

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 1. 대시보드 화면 API
# ==========================================
@router.get("/dashboard/{cik}")
async def get_dashboard(request: Request, cik: str, db: Session = Depends(get_db)):
    try:
        # 1. 기관 찾기
        saved_inst = db.query(Institution).filter(Institution.cik == cik).first()
        
        if not saved_inst:
             # error.html이 없으면 500 에러가 나므로, 안전하게 문자열 반환하거나 404 처리
             raise HTTPException(status_code=404, detail="Institution not found")

        # 위키피디아 검색 로직
        if not saved_inst.description:
            print(f"🔍 {saved_inst.name}에 대한 위키피디아 검색 중...")
            wiki_desc = await get_company_description("", saved_inst.name)
            
            if wiki_desc and "찾을 수 없습니다" not in wiki_desc:
                saved_inst.description = wiki_desc
                db.commit() 
                print("✅ 위키 데이터 저장 완료!")

        # 2. 보유 종목 쿼리
        top_holdings_query = (
            db.query(
                Holding.ticker,
                func.max(Holding.name).label("name"),
                func.sum(Holding.value).label("value"),
                func.sum(Holding.shares).label("shares"),
                func.avg(Holding.change_rate).label("change_rate"),
                Holding.holding_type
            )
            .filter(Holding.institution_id == saved_inst.id)
            .group_by(Holding.ticker, Holding.holding_type)
            .order_by(desc(func.sum(Holding.value)))
            .limit(100)
            .all()
        )

        total_assets = db.query(func.sum(Holding.value)).filter(
            Holding.institution_id == saved_inst.id
        ).scalar() or 0

        # 🚨 [핵심 수정] Decimal -> int/float 강제 변환
        # DB에서 가져온 집계 결과(func.sum 등)가 Decimal 타입일 경우 JSON 변환이 안 됩니다.
        display_holdings = []
        for h in top_holdings_query:
            display_holdings.append({
                "display_name": h.name or "Unknown",
                "ticker": h.ticker,
                # 👇 여기가 수정되었습니다 (int, float로 감싸주기)
                "value": int(h.value) if h.value else 0,
                "shares": int(h.shares) if h.shares else 0,
                "change_rate": float(h.change_rate) if h.change_rate else 0.0,
                "holding_type": h.holding_type,
            })

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": saved_inst.name or f"Institution ({cik})",
            "report_date": "2025-09-30",
            "holdings": display_holdings,
            "description": saved_inst.description or "",
            "total_assets": int(total_assets) # 여기도 int 변환
        })
        
    except Exception as e:
        print(f"Dashboard Error: {e}")
        # error.html이 있으면 그걸 보여주고, 없으면 그냥 에러 메시지 출력
        try:
            return templates.TemplateResponse("error.html", {"request": request, "message": "데이터 로딩 실패"})
        except:
            return {"error": f"Server Error: {str(e)}"}


# ==========================================
# 2. 🤖 AI 분석 API
# ==========================================
@router.get("/dashboard/{cik}/ai-analysis")
async def get_ai_analysis_endpoint(cik: str, db: Session = Depends(get_db)):
    try:
        institution = db.query(Institution).filter(Institution.cik == cik).first()
        if not institution:
            return {"analysis": "기관 정보를 찾을 수 없습니다."}

        if institution.ai_summary and len(institution.ai_summary) > 10:
            return {"analysis": institution.ai_summary}

        top_holdings = db.query(Holding)\
            .filter(Holding.institution_id == institution.id)\
            .order_by(Holding.value.desc())\
            .limit(20).all()

        if not top_holdings:
            return {"analysis": "분석할 보유 종목 데이터가 없습니다."}

        holdings_list = []
        for h in top_holdings:
            name = getattr(h, "name", getattr(h, "name_of_issuer", "Unknown"))
            # 👇 여기도 안전하게 변환
            change = float(h.change_rate) if h.change_rate is not None else 0.0
            val = int(h.value) if h.value else 0
            
            holdings_list.append({
                "name_of_issuer": name, 
                "value": val,
                "change_rate": change
            })

        analysis_result = await analyze_portfolio_by_llm(holdings_list, institution.name)

        if analysis_result and "오류" not in analysis_result:
            institution.ai_summary = analysis_result
            db.commit()

        return {"analysis": analysis_result}

    except Exception as e:
        print(f"🔥 AI 분석 에러: {e}")
        return {"analysis": "현재 AI 분석 서버가 응답하지 않습니다."}