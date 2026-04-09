import time, requests, hashlib, hmac, base64, os
import pandas as pd
import xml.etree.ElementTree as ET

# API 키 설정
keys = {
    "AD_API": os.environ.get("AD_API_KEY", ""),
    "AD_SEC": os.environ.get("AD_SECRET_KEY", ""),
    "AD_CUS": os.environ.get("AD_CUSTOMER_ID", ""),
    "ID": os.environ.get("OPEN_CLIENT_ID", ""),
    "SEC": os.environ.get("OPEN_CLIENT_SECRET", "")
}

def get_keywords():
    try:
        res = requests.get("https://trends.google.com/trending/rss?geo=KR")
        if res.status_code != 200: return []
        seeds = [i.find('title').text for i in ET.fromstring(res.content).findall('.//item')]
        
        if not seeds: return []
        
        # 네이버 API 호출용 헤더 생성
        hint = ",".join(seeds[:5]).replace(" ", "")
        ts = str(round(time.time() * 1000))
        msg = f"{ts}.GET./keywordstool"
        sign = base64.b64encode(hmac.new(bytes(keys["AD_SEC"], "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()).decode("utf-8")
        
        headers = {"X-Timestamp": ts, "X-API-KEY": keys["AD_API"], "X-Customer": str(keys["AD_CUS"]), "X-Signature": sign}
        r = requests.get("https://api.searchad.naver.com/keywordstool", params={"hintKeywords": hint, "showDetail": 1}, headers=headers)
        
        if r.status_code == 200:
            data = r.json().get('keywordList', [])
            return [{"키워드": i['relKeyword'], "검색량": int(i.get('monthlyPcQcCnt',0)) + int(i.get('monthlyMobileQcCnt',0))} for i in data]
        else:
            print(f"네이버 API 응답 에러: {r.status_code}")
            return []
    except Exception as e:
        print(f"오류 발생: {e}")
        return []

if __name__ == "__main__":
    print("🚀 분석 시작...")
    results = get_keywords()
    
    if results:
        df = pd.DataFrame(results).sort_values(by="검색량", ascending=False).head(100)
        df.to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
        print(f"✅ {len(df)}개의 키워드 저장 완료!")
    else:
        # 데이터가 없을 경우 빈 파일이라도 생성하여 에러 방지
        pd.DataFrame(columns=["키워드", "검색량"]).to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
        print("⚠️ 수집된 데이터가 없어 빈 파일을 생성했습니다.")
