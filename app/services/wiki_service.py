import httpx
import asyncio

# 🚨 브라우저인 척 속이는 헤더 (필수!)
WIKI_HEADERS = {
    "User-Agent": "Easy13F_Project/1.0 (kang203062@gmail.com)",
    "Accept-Encoding": "gzip, deflate"
}

async def get_company_description(ticker: str, institution_name: str) -> str:
    """
    라이브러리 없이 직접 위키피디아 API를 호출합니다. (가장 빠름)
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 검색어 후보: 기관명 우선, 그 다음 티커
        queries = [institution_name, f"{institution_name} (company)", ticker]
        
        for query in queries:
            if not query: continue
            
            try:
                # 1. 페이지 제목 찾기
                search_url = "https://en.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 1
                }
                
                resp = await client.get(search_url, params=params, headers=WIKI_HEADERS)
                data = resp.json()
                
                if not data.get("query", {}).get("search"):
                    continue
                
                # 2. 요약 내용 가져오기
                page_title = data["query"]["search"][0]["title"]
                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title}"
                
                summary_resp = await client.get(summary_url, headers=WIKI_HEADERS)
                
                if summary_resp.status_code == 200:
                    summary_data = summary_resp.json()
                    extract = summary_data.get("extract", "")
                    if extract:
                        return extract # 성공하면 바로 리턴
                        
            except Exception as e:
                print(f"Wiki Error ({query}): {e}")
                continue

    return "위키피디아 정보를 찾을 수 없습니다."