import wikipedia
import asyncio

# 1. 위키피디아 설정 (언어 및 차단 방지용 User-Agent)
wikipedia.set_lang("en")
# 라이브러리 내부 정책에 따라 User-Agent를 설정합니다.
try:
    wikipedia.set_user_agent("Easy13F_Student_Project/1.0 (kang203062@gmail.com)")
except AttributeError:
    pass # 구버전일 경우 패스

async def get_company_description(ticker: str, institution_name: str) -> str:
    """
    wikipedia 라이브러리를 사용하여 기업 설명을 가져옵니다.
    (동기 함수인 wikipedia를 비동기 환경에서 쓰기 위해 thread로 실행)
    """
    return await asyncio.to_thread(fetch_wikipedia_sync, ticker, institution_name)

def fetch_wikipedia_sync(ticker: str, institution_name: str) -> str:
    queries = [institution_name, f"{institution_name} (company)", ticker]
    
    for query in queries:
        try:
            # sentences=3 : 딱 3문장만 가져와서 로딩 속도 향상
            summary = wikipedia.summary(query, sentences=3, auto_suggest=False)
            if summary:
                return summary
        except wikipedia.exceptions.DisambiguationError as e:
            # 검색 결과가 여러 개일 경우 첫 번째 것 시도
            try:
                return wikipedia.summary(e.options[0], sentences=3, auto_suggest=False)
            except:
                continue
        except wikipedia.exceptions.PageError:
            continue # 페이지 없으면 다음 검색어 시도
        except Exception:
            continue
            
    return "위키피디아에서 정보를 찾을 수 없습니다."