import httpx
import asyncio

# 🚨 [핵심 수정] 위키피디아도 User-Agent가 필수입니다!
WIKI_HEADERS = {
    "User-Agent": "Easy13F_Project/1.0 (kang203062@gmail.com)",
    "Accept-Encoding": "gzip, deflate"
}

async def get_company_description(ticker: str, institution_name: str) -> str:
    """
    위키피디아 API를 통해 기업/기관 설명을 가져옵니다.
    1순위: 기관명 검색 / 2순위: 티커 검색
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 검색어 후보군 (기관명 우선)
        queries = [institution_name, ticker]
        
        for query in queries:
            if not query: continue
            
            try:
                # 1. 위키피디아 검색 (페이지 제목 찾기)
                search_url = "https://en.wikipedia.org/w/api.php"
                search_params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 1
                }
                
                # 🚨 헤더 추가
                resp = await client.get(search_url, params=search_params, headers=WIKI_HEADERS)
                data = resp.json()
                
                if not data.get("query", {}).get("search"):
                    continue
                    
                page_title = data["query"]["search"][0]["title"]
                
                # 2. 상세 내용 가져오기 (요약본)
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title}"
                
                # 🚨 헤더 추가
                summary_resp = await client.get(summary_url, headers=WIKI_HEADERS)
                
                if summary_resp.status_code == 200:
                    summary_data = summary_resp.json()
                    extract = summary_data.get("extract", "")
                    if extract:
                        return extract  # 성공하면 바로 반환
                        
            except Exception as e:
                print(f"⚠️ Wiki Error ({query}): {e}")
                continue

    return "해당 기관에 대한 위키피디아 정보를 찾을 수 없습니다."