from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.db.database import get_db
from app.db.models import Institution, Holding
# 🚨 서비스 파일들 임포트 (파일이 실제로 존재해야 합니다!)
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm 
from app.services.wiki_service import get_company_description # 👈 위키피디아 임포트

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
             return templates.TemplateResponse("error.html", {"request": request, "message": "기관을 찾을 수 없습니다."})

        # 🚨 [복구 완료] 위키피디아 데이터 가져오기
        # 설명이 비어있으면 위키피디아 검색을 시도합니다.
        if not saved_inst.description:
            print(f"🔍 {saved_inst.name}에 대한 위키피디아 검색 중...")
            
            # 💡 [핵심 수정] wiki_service가 'async' 함수이므로 'await'를 꼭 써야 합니다!
            # 인자 순서: (ticker, institution_name) -> 기관이라 티커는 없으니 빈칸("")으로 보냄
            wiki_desc = await get_company_description("", saved_inst.name)
            
            # "정보를 찾을 수 없습니다"가 아닐 때만 저장
            if wiki_desc and "찾을 수 없습니다" not in wiki_desc:
                saved_inst.description = wiki_desc
                db.commit() # DB에 영구 저장
                print("✅ 위키 데이터 저장 완료!")

        # 2. 보유 종목 (메모리 보호: 중복 합산 + 100개 제한)
        top_holdings_query = (
            db.query(
                Holding.ticker,
                func.max(Holding.name).label("name"),           # 이름
                func.sum(Holding.value).label("value"),         # 가치 합산
                func.sum(Holding.shares).label("shares"),       # 주식 수 합산
                func.avg(Holding.change_rate).label("change_rate"), # 변동률 평균
                Holding.holding_type
            )
            .filter(Holding.institution_id == saved_inst.id)
            .group_by(Holding.ticker, Holding.holding_type)     # 티커로 그룹화
            .order_by(desc(func.sum(Holding.value)))            # 가치 순 정렬
            .limit(100)                                         # 100개 제한
            .all()
        )

        # 총 자산 가치 별도 계산
        total_assets = db.query(func.sum(Holding.value)).filter(
            Holding.institution_id == saved_inst.id
        ).scalar() or 0

        # 데이터 변환 (템플릿용)
        display_holdings = []
        for h in top_holdings_query:
            display_holdings.append({
                "display_name": h.name or "Unknown",
                "ticker": h.ticker,
                "value": h.value,
                "shares": h.shares,
                "change_rate": round(h.change_rate, 2) if h.change_rate else 0,
                "holding_type": h.holding_type,
            })

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": saved_inst.name or f"Institution ({cik})",
            "report_date": "2025-09-30",
            "holdings": display_holdings,
            "description": saved_inst.description or "", # 이제 여기에 위키 내용이 들어갑니다!
            "total_assets": total_assets
        })
        
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return templates.TemplateResponse("error.html", {"request": request, "message": "데이터 로딩 실패"})


# ==========================================
# 2. 🤖 AI 분석 API
# ==========================================
@router.get("/dashboard/{cik}/ai-analysis")
async def get_ai_analysis_endpoint(cik: str, db: Session = Depends(get_db)):
    try:
        # 1. 기관 찾기
        institution = db.query(Institution).filter(Institution.cik == cik).first()
        if not institution:
            return {"analysis": "기관 정보를 찾을 수 없습니다."}

        # 2. [캐시 확인] 이미 분석한 내용이 있으면 반환
        if institution.ai_summary and len(institution.ai_summary) > 10:
            return {"analysis": institution.ai_summary}

        # 3. [데이터 확보] 분석할 상위 20개 종목만 가져오기
        top_holdings = db.query(Holding)\
            .filter(Holding.institution_id == institution.id)\
            .order_by(Holding.value.desc())\
            .limit(20).all()

        if not top_holdings:
            return {"analysis": "분석할 보유 종목 데이터가 없습니다."}

        # 4. 프롬프트용 데이터 포장
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

        # 6. 결과 저장
        if analysis_result and "오류" not in analysis_result:
            institution.ai_summary = analysis_result
            db.commit()

        return {"analysis": analysis_result}

    except Exception as e:
        print(f"🔥 AI 분석 에러: {e}")
        return {"analysis": "현재 AI 분석 서버가 응답하지 않습니다. (잠시 후 다시 시도해주세요)"}