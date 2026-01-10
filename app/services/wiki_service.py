import wikipedia

def get_company_description(query: str) -> str:
    """
    [수정됨] 위키백과에서 가장 정확한 회사 메인 페이지의 '요약문'만 가져옵니다.
    """
    try:
        # 1. 언어 설정
        wikipedia.set_lang("en")
        
        # 2. 검색어 정제 (Inc, Corp 등 제거하고 순수 이름만)
        clean_name = query.replace(" Inc", "").replace(" Corp", "").replace(" L.P.", "").replace(" plc", "").strip()
        
        # 3. [핵심 변경] search() 대신 summary()를 바로 시도합니다.
        # auto_suggest=False: 엉뚱한 거 추천받지 말고 내 검색어 그대로 찾아라
        try:
            summary = wikipedia.summary(clean_name, sentences=4, auto_suggest=False)
            return summary
        except wikipedia.exceptions.DisambiguationError as e:
            # 동명이인이 많으면 첫 번째 추천어로 재시도
            return wikipedia.summary(e.options[0], sentences=4)
        except wikipedia.exceptions.PageError:
            # 페이지 없으면 검색으로 선회
            search_res = wikipedia.search(clean_name, results=1)
            if search_res:
                return wikipedia.summary(search_res[0], sentences=4)
            
        return ""

    except Exception as e:
        print(f"⚠️ 위키백과 검색 실패: {e}")
        return ""