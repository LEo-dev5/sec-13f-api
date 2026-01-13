from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from app.db.database import get_db
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm
from app.services.wiki_service import get_company_description
from sqlalchemy import desc, func # 👈 func 추가 (총 자산 계산용)

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 1. 대시보드 화면 API
# ==========================================
@router.get("/dashboard/{cik}")
async def get_dashboard(request: Request, cik: str, db: Session = Depends(get_db)):
    institution_name = ""
    report_date = "2025-09-30" 
    description_text = ""
    display_holdings = []
    total_assets = 0 # 총 자산 변수 추가
    
    try:
        # 1. DB 확인
        saved_inst = db.query(Institution).filter(Institution.cik == cik).first()
        
        if saved_inst:
            # 이름 복구 로직 (기존 유지)
            if not saved_inst.name:
                try:
                    fresh_data = await fetch_latest_13f(cik)
                    saved_inst.name = fresh_data.institution_name
                    db.commit()
                except:
                    saved_inst.name = f"Institution ({cik})"
            
            institution_name = saved_inst.name
            
            # 설명 가져오기 (기존 유지)
            if saved_inst.description:
                description_text = saved_inst.description

            # 🚨 [핵심 수정] 메모리 폭발 방지 로직
            # 기존: for h in saved_inst.holdings: (전체 로드 -> 램 부족)
            # 변경: DB에서 상위 100개만 쿼리하여 가져옴
            
            # A. 상위 100개 종목 가져오기
            top_holdings = db.query(Holding).filter(
                Holding.institution_id == saved_inst.id
            ).order_by(desc(Holding.value)).limit(100).all()

            # B. 총 자산 가치 별도 계산 (전체 합산)
            # 100개만 가져왔으므로 전체 합계는 DB에 계산을 시켜야 정확함
            total_assets = db.query(func.sum(Holding.value)).filter(
                Holding.institution_id == saved_inst.id
            ).scalar() or 0

            # 리스트에 담기
            for h in top_holdings:
                display_holdings.append({
                    "display_name": getattr(h, "name", getattr(h, "name_of_issuer", "Unknown")),
                    "ticker": h.ticker,
                    "value": h.value,
                    "shares": h.shares,
                    "change_rate": h.change_rate,
                    "holding_type": h.holding_type,
                })

        else:
            # DB에 없으면 크롤링 (기존 로직 유지)
            filing_data = await fetch_latest_13f(cik)
            institution_name = filing_data.institution_name
            if filing_data.period_of_report:
                report_date = filing_data.period_of_report

            # 크롤링 데이터도 100개만
            for h in filing_data.holdings[:100]:
                h_dict = h.dict()
                h_dict['display_name'] = h.name_of_issuer
                display_holdings.append(h_dict)
                # 크롤링한 데이터에서 총 자산 계산
                if h.value:
                    total_assets += h.value

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": institution_name,
            "report_date": report_date,
            "holdings": display_holdings,
            "description": description_text,
            "total_assets": total_assets # 템플릿에서 총 자산 표시 가능하도록 추가
        })
        
    except Exception as e:
        print(f"🔥 대시보드 에러: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": "Error Loading Data",
            "report_date": "-",
            "holdings": [],
            "description": "",
            "total_assets": 0
        })

# ==========================================
# 2. 🤖 AI 분석 API (기존 유지)
# ==========================================
@router.get("/dashboard/{cik}/ai-analysis")
async def get_ai_analysis_endpoint(cik: str, db: Session = Depends(get_db)):
    try:
        # 1. 기관 찾기
        institution = db.query(Institution).filter(Institution.cik == cik).first()
        if not institution:
            return {"analysis": "기관 정보를 찾을 수 없습니다."}

        # 2. [캐시 확인]
        if institution.ai_summary and len(institution.ai_summary) > 10:
            return {"analysis": institution.ai_summary}

        # 3. [데이터 확보]
        top_holdings = db.query(Holding)\
            .filter(Holding.institution_id == institution.id)\
            .order_by(Holding.value.desc())\
            .limit(20).all()

        if not top_holdings:
            return {"analysis": "분석할 보유 종목 데이터가 없습니다."}

        # 4. 데이터 포장
        holdings_list = []
        for h in top_holdings:
            name = getattr(h, "name", getattr(h, "name_of_issuer", "Unknown"))
            change = h.change_rate if h.change_rate is not None else 0
            holdings_list.append({
                "name_of_issuer": name, 
                "value": h.value,
                "change_rate": change
            })

        # 5. AI 서비스 호출
        analysis_result = await analyze_portfolio_by_llm(holdings_list, institution.name)

        # 6. 저장
        if analysis_result and "오류" not in analysis_result:
            institution.ai_summary = analysis_result
            db.commit()

        return {"analysis": analysis_result}

    except Exception as e:
        print(f"🔥 AI 분석 에러: {e}")
        return {"analysis": "현재 AI 분석 서버가 응답하지 않습니다."}