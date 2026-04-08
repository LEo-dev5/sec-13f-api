from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.db.database import get_db
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm
from app.services.wiki_service import get_company_description
from app.services.db_service import update_institution_to_db

router = APIRouter()


# ==========================================
# 1. 기관 목록 조회
# ==========================================
@router.get("/institutions")
async def list_institutions(
    skip: int = 0,
    limit: int = 50,
    featured_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Institution)
    if featured_only:
        query = query.filter(Institution.is_featured == True)
    institutions = query.offset(skip).limit(limit).all()
    return {
        "total": query.count(),
        "institutions": [
            {"cik": i.cik, "name": i.name, "is_featured": i.is_featured}
            for i in institutions
        ],
    }


# ==========================================
# 2. 기관 상세 조회 (보유 종목 포함)
# ==========================================
@router.get("/institution/{cik}")
async def get_institution(cik: str, db: Session = Depends(get_db)):
    inst = db.query(Institution).filter(Institution.cik == cik).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    # 위키피디아 설명 지연 로드
    if not inst.description:
        wiki_desc = await get_company_description("", inst.name)
        if wiki_desc and "찾을 수 없습니다" not in wiki_desc:
            inst.description = wiki_desc
            db.commit()

    holdings_query = (
        db.query(
            Holding.ticker,
            func.max(Holding.name).label("name"),
            func.sum(Holding.value).label("value"),
            func.sum(Holding.shares).label("shares"),
            func.avg(Holding.change_rate).label("change_rate"),
            Holding.holding_type,
        )
        .filter(Holding.institution_id == inst.id)
        .group_by(Holding.ticker, Holding.holding_type)
        .order_by(desc(func.sum(Holding.value)))
        .limit(100)
        .all()
    )

    total_assets = (
        db.query(func.sum(Holding.value))
        .filter(Holding.institution_id == inst.id)
        .scalar()
        or 0
    )

    return {
        "cik": cik,
        "name": inst.name,
        "is_featured": inst.is_featured,
        "description": inst.description or "",
        "total_assets": int(total_assets),
        "holdings": [
            {
                "ticker": h.ticker,
                "name": h.name or "Unknown",
                "value": int(h.value) if h.value else 0,
                "shares": int(h.shares) if h.shares else 0,
                "change_rate": float(h.change_rate) if h.change_rate else 0.0,
                "holding_type": h.holding_type,
            }
            for h in holdings_query
        ],
    }


# ==========================================
# 3. SEC에서 최신 13F 데이터 직접 조회 (DB 저장 없음)
# ==========================================
@router.get("/institution/{cik}/live")
async def get_live_filing(cik: str):
    try:
        filing = await fetch_latest_13f(cik)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SEC 데이터 조회 실패: {str(e)}")

    return {
        "cik": filing.cik,
        "institution_name": filing.institution_name,
        "report_date": filing.report_date,
        "holdings": [
            {
                "name_of_issuer": h.name_of_issuer,
                "cusip": h.cusip,
                "ticker": h.ticker,
                "value": h.value,
                "shares": h.shares,
                "change_rate": h.change_rate,
                "holding_type": h.holding_type,
            }
            for h in filing.holdings
        ],
    }


# ==========================================
# 4. 기관 데이터 동기화 (SEC → DB)
# ==========================================
@router.post("/institution/{cik}/sync")
async def sync_institution(
    cik: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background_tasks.add_task(update_institution_to_db, db, cik)
    return {"status": "accepted", "message": f"CIK {cik} 동기화가 백그라운드에서 시작되었습니다."}


# ==========================================
# 5. AI 포트폴리오 분석
# ==========================================
@router.get("/institution/{cik}/ai-analysis")
async def get_ai_analysis(cik: str, db: Session = Depends(get_db)):
    institution = db.query(Institution).filter(Institution.cik == cik).first()
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")

    if institution.ai_summary and len(institution.ai_summary) > 10:
        return {"analysis": institution.ai_summary, "cached": True}

    top_holdings = (
        db.query(Holding)
        .filter(Holding.institution_id == institution.id)
        .order_by(Holding.value.desc())
        .limit(20)
        .all()
    )

    if not top_holdings:
        return {"analysis": "분석할 보유 종목 데이터가 없습니다.", "cached": False}

    holdings_list = [
        {
            "name_of_issuer": h.name or "Unknown",
            "value": int(h.value) if h.value else 0,
            "change_rate": float(h.change_rate) if h.change_rate is not None else 0.0,
        }
        for h in top_holdings
    ]

    analysis_result = await analyze_portfolio_by_llm(holdings_list, institution.name)

    if analysis_result and "오류" not in analysis_result:
        institution.ai_summary = analysis_result
        db.commit()

    return {"analysis": analysis_result, "cached": False}
