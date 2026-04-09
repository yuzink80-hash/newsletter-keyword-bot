import time
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import os

# 1. 시스템 환경 변수에서 API 키 불러오기
AD_API_KEY = os.environ.get("AD_API_KEY")
AD_SECRET_KEY = os.environ.get("AD_SECRET_KEY")
AD_CUSTOMER_ID = os.environ.get("AD_CUSTOMER_ID")
OPEN_CLIENT_ID = os.environ.get("OPEN_CLIENT_ID")
OPEN_CLIENT_SECRET = os.environ.get("OPEN_CLIENT_SECRET")

def expand_keywords_bulk(seeds):
    if not seeds:
        print("⚠️ 시드 키워드가 없어 확장을 중단합니다.")
        return []
    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    method = "GET"
    sample_seeds = [seeds.pop(0) for _ in range(min(5, len(seeds)))]
    hint_str = ",".join(sample_seeds).replace(" ", "")
    print(f"🔎 네이버 API 호출 시도 (힌트: {hint_str})")
    
    timestamp = str(round(time.time() * 1000))
    message = timestamp + "." + method + "." + uri
    
    try:
        # Secret Key가 비어있는지 확인
        if not AD_SECRET_KEY:
            print("🚨 에러: AD_SECRET_KEY가 설정되지 않았습니다. GitHub Secrets를 확인하세요.")
            return []
            
        hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
        signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
        headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_API_KEY, "X-Customer": str(AD_CUSTOMER_ID), "X-Signature": signature}
        params = {"hintKeywords": hint_str, "showDetail": 1}
        response = requests.get(base_url + uri, params=params, headers=headers)
        
        if response.status_code == 200:
            raw_list = response.json().get('keywordList', [])
            print(f"✅ 연관 키워드 {len(raw_list)}개 수집 성공!")
            return [{"keyword": i.get('relKeyword'), "volume": (int(i.get('monthlyPcQcCnt', 0)) if str(i.get('monthlyPcQcCnt')).isdigit() else 10) + (int(i.get('monthlyMobileQcCnt', 0)) if str(i.get('monthlyMobileQcCnt')).isdigit() else 10)} for i in raw_list]
        else:
            print(f"❌ 네이버 API 호출 실패 (코드: {response.status_code})")
            print(f"응답 메시지: {response.text}")
            return []
    except Exception as e:
        print(f"🚨 시스템 에러: {e}")
        return []

def get_document_count(keyword):
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET}
    try:
        res = requests.get(url, params={"query": keyword, "display": 1}, headers=headers)
        return res.json().get('total', 0) if res.status_code == 200 else 0
    except: return 0

if __name__ == "__main__":
    print("🚀 분석 시작...")
    res = requests.get("https://trends.google.com/trending/rss?geo=KR")
    seeds = [item.find('title').text for item in ET.fromstring(res.content).findall('.//item')] if res.status_code == 200 else []
    print(f"📈 구글 트렌드 키워드 {len(seeds)}개 발견")

    raw_keywords = expand_keywords_bulk(seeds)
    if not raw_keywords:
        print("⚠️ 수집된 데이터가 없습니다. API 키 설정이나 권한을 확인해주세요.")
    else:
        df = pd.DataFrame(raw_keywords)
        if 'volume' in df.columns:
            top = df.sort_values(by="volume", ascending=False).head(100)
            final = []
            for item in top.to_dict('records'):
                doc = get_document_count(item['keyword'])
                vol = item['volume']
                final.append({"키워드": item['keyword'], "검색량": vol, "문서수": doc, "경쟁강도": round(doc/vol, 2) if vol > 0 else 0})
                time.sleep(0.1)
            pd.DataFrame(final).sort_values(by=["경쟁강도", "검색량"], ascending=[True, False]).to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
            print("✅ daily_golden_keywords.csv 생성 완료!")
        else:
            print("🚨 데이터에 'volume' 정보가 없습니다.")
