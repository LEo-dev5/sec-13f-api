from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from app.db.database import get_db
from app.db.models import Institution, Holding
from app.services.sec_service import fetch_latest_13f
from app.services.ai_service import analyze_portfolio_by_llm
from app.services.wiki_service import get_company_description

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

# ==========================================
# 1. 대시보드 화면 API (회사 소개 즉시 로딩)
# ==========================================
@router.get("/dashboard/{cik}")
async def get_dashboard(request: Request, cik: str, db: Session = Depends(get_db)):
    institution_name = ""
    report_date = ""
    description_text = ""
    display_holdings = []
    
    try:
        # 1. DB 확인 (이름 없으면 SEC에서 복구)
        saved_inst = db.query(Institution).filter(Institution.cik == cik).first()
        
        if saved_inst:
            # [안전장치] 이름이 없으면 복구
            if not saved_inst.name:
                print(f"⚠️ {cik} 이름 복구 시도...")
                try:
                    fresh_data = await fetch_latest_13f(cik)
                    saved_inst.name = fresh_data.institution_name
                    db.commit()
                except:
                    saved_inst.name = f"Institution ({cik})"
            
            institution_name = saved_inst.name
            
            # [설명] 회사 개요 가져오기
            if saved_inst.description:
                description_text = saved_inst.description
            else:
                # 없으면 위키백과 검색 (비동기 처리 방지 위해 일단 빈칸, 다음 로직에서 처리됨)
                pass 

            # [보유종목] 데이터 변환
            if saved_inst.holdings:
                for h in saved_inst.holdings:
                    display_holdings.append({
                        "display_name": getattr(h, "name", getattr(h, "name_of_issuer", "Unknown")),
                        "ticker": h.ticker,
                        "value": h.value,
                        "shares": h.shares,
                        "change_rate": h.change_rate,
                        "holding_type": h.holding_type,
                    })
        else:
            # DB에 아예 없으면 크롤링
            filing_data = await fetch_latest_13f(cik)
            institution_name = filing_data.institution_name
            # 크롤링 데이터 변환
            for h in filing_data.holdings[:100]:
                h_dict = h.dict()
                h_dict['display_name'] = h.name_of_issuer
                display_holdings.append(h_dict)

        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": institution_name,
            "report_date": report_date,
            "holdings": display_holdings,
            "description": description_text
        })
        
    except Exception as e:
        print(f"🔥 대시보드 에러: {e}")
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "cik": cik,
            "institution_name": "Error Loading Data",
            "report_date": "-",
            "holdings": [],
            "description": ""
        })

# ==========================================
# 2. 🤖 AI 분석 API (여기가 핵심!)
# ==========================================
@router.get("/dashboard/{cik}/ai-analysis")
async def get_ai_analysis_endpoint(cik: str, db: Session = Depends(get_db)):
    try:
        print(f"📡 [AI 요청] {cik} 분석 시작...")
        
        # 1. 기관 찾기
        institution = db.query(Institution).filter(Institution.cik == cik).first()
        if not institution:
            return {"analysis": "기관 정보를 찾을 수 없습니다."}

        # 2. [캐시 확인] 이미 분석한 게 있으면 바로 반환
        if institution.ai_summary and len(institution.ai_summary) > 10:
            print(f"✨ [AI Cache] 저장된 분석글 반환")
            return {"analysis": institution.ai_summary}

        # 3. [데이터 확보] 관계형 데이터가 불안정할 수 있으니 직접 쿼리 (강제 로딩)
        # 상위 20개 종목을 가치순으로 정렬해서 가져옴
        top_holdings = db.query(Holding)\
            .filter(Holding.institution_id == institution.id)\
            .order_by(Holding.value.desc())\
            .limit(20).all()

        if not top_holdings:
            return {"analysis": "분석할 보유 종목 데이터가 없습니다."}

        # 4. 데이터 포장 (AI에게 보낼 도시락 싸기)
        holdings_list = []
        for h in top_holdings:
            # 안전하게 이름 가져오기
            name = getattr(h, "name", getattr(h, "name_of_issuer", "Unknown"))
            change = h.change_rate if h.change_rate is not None else 0
            holdings_list.append({
                "name_of_issuer": name, 
                "value": h.value,
                "change_rate": change
            })

        # 5. AI 서비스 호출 (시간이 좀 걸림 ⏳)
        print(f"🧠 [AI Thinking] Ollama에게 분석 요청 중... ({institution.name})")
        analysis_result = await analyze_portfolio_by_llm(holdings_list, institution.name)

        # 6. 결과 저장 및 반환
        if analysis_result and "오류" not in analysis_result:
            institution.ai_summary = analysis_result
            db.commit()
            print(f"💾 [AI Saved] 분석 완료 및 저장!")
        else:
            print(f"⚠️ [AI Fail] 결과가 비어있거나 오류 발생")

        return {"analysis": analysis_result}

    except Exception as e:
        print(f"🔥 AI 분석 엔드포인트 치명적 에러: {e}")
        return {"analysis": "현재 AI 분석 서버가 응답하지 않습니다. (잠시 후 다시 시도해주세요)"}