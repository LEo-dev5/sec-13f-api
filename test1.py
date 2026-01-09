# Easy13F/test.py
import asyncio
from app.services.sec_service import fetch_latest_13f

# 비동기 함수를 실행하기 위한 껍데기
async def main():
    try:
        # 워렌 버핏의 버크셔 해서웨이 CIK
        cik = "0001067983" 
        print(f"CIK {cik} 데이터 수집 시작...")
        
# ... (앞부분 동일) ...

        result = await fetch_latest_13f(cik)
        
        print(f"보고서 날짜: {result.report_date}")
        print(f"가져온 종목 수: {len(result.holdings)}개")
        
        if result.holdings:  # 👈 데이터가 있을 때만 출력하도록 조건문 추가
            print("첫 번째 종목 샘플:", result.holdings[0])
        else:
            print("데이터가 없습니다. (URL 문제거나 Cover Page만 가져왔을 수 있음)")
            
# ... (뒷부분 동일) ...
        
    except Exception as e:
        print(f"에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())