import time, requests, hashlib, hmac, base64, os
import pandas as pd
import xml.etree.ElementTree as ET

# 키 로딩 및 유효성 체크
keys = {
    "AD_API": os.environ.get("AD_API_KEY"),
    "AD_SEC": os.environ.get("AD_SECRET_KEY"),
    "AD_CUS": os.environ.get("AD_CUSTOMER_ID"),
    "ID": os.environ.get("OPEN_CLIENT_ID"),
    "SEC": os.environ.get("OPEN_CLIENT_SECRET")
}

def expand():
    res = requests.get("https://trends.google.com/trending/rss?geo=KR")
    seeds = [i.find('title').text for i in ET.fromstring(res.content).findall('.//item')] if res.status_code==200 else []
    if not seeds: return []
    
    hint = ",".join(seeds[:5]).replace(" ", "")
    ts = str(round(time.time() * 1000))
    msg = ts + ".GET./keywordstool"
    sign = base64.b64encode(hmac.new(bytes(keys["AD_SEC"], "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()).decode("utf-8")
    
    headers = {"X-Timestamp": ts, "X-API-KEY": keys["AD_API"], "X-Customer": str(keys["AD_CUS"]), "X-Signature": sign}
    r = requests.get("https://api.searchad.naver.com/keywordstool", params={"hintKeywords": hint, "showDetail": 1}, headers=headers)
    
    if r.status_code != 200:
        print(f"❌ 네이버 API 에러: {r.status_code}, {r.text}")
        return []
    
    data = r.json().get('keywordList', [])
    return [{"keyword": i['relKeyword'], "volume": int(i.get('monthlyPcQcCnt',0)) + int(i.get('monthlyMobileQcCnt',0))} for i in data]

if __name__ == "__main__":
    print("🚀 작업 시작...")
    raw = expand()
    if raw:
        df = pd.DataFrame(raw).sort_values(by="volume", ascending=False).head(50)
        # 블로그 문서수 조회 생략(빠른 테스트용) 또는 포함
        df.to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
        print("✅ 파일 생성 성공!")
    else:
        print("🚨 데이터 수집 실패")
