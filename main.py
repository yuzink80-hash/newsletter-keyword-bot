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
    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    method = "GET"
    hint_str = ",".join(seeds.pop(0) for _ in range(min(5, len(seeds))))
    hint_str = hint_str.replace(" ", "")
    timestamp = str(round(time.time() * 1000))
    message = timestamp + "." + method + "." + uri
    hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
    signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
    headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_API_KEY, "X-Customer": str(AD_CUSTOMER_ID), "X-Signature": signature}
    params = {"hintKeywords": hint_str, "showDetail": 1}
    response = requests.get(base_url + uri, params=params, headers=headers)
    expanded_list = list()
    if response.status_code == 200:
        data = response.json()
        raw_list = data.get('keywordList', list())
        for item in raw_list:
            pc = int(item.get('monthlyPcQcCnt', 0)) if str(item.get('monthlyPcQcCnt')).isdigit() else 10
            mo = int(item.get('monthlyMobileQcCnt', 0)) if str(item.get('monthlyMobileQcCnt')).isdigit() else 10
            expanded_list.append({"keyword": item.get('relKeyword'), "volume": pc + mo})
    return expanded_list

def get_document_count(keyword):
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET}
    params = {"query": keyword, "display": 1}
    response = requests.get(url, params=params, headers=headers)
    return response.json().get('total', 0) if response.status_code == 200 else 0

# 메인 실행부
if __name__ == "__main__":
    print("🚀 트렌드 수집 및 분석 시작...")
    url = "https://trends.google.com/trending/rss?geo=KR"
    res = requests.get(url)
    seeds = list()
    if res.status_code == 200:
        root = ET.fromstring(res.content)
        for item in root.findall('.//item'):
            seeds.append(item.find('title').text)

    raw_keywords = expand_keywords_bulk(seeds)
    df_raw = pd.DataFrame(raw_keywords)
    df_top100 = df_raw.sort_values(by="volume", ascending=False).head(100)

    final_results = list()
    for item in df_top100.to_dict('records'):
        kw, vol = item['keyword'], item['volume']
        doc = get_document_count(kw)
        comp = round(doc / vol, 2) if vol > 0 else 0
        final_results.append({"키워드": kw, "검색량": vol, "문서수": doc, "경쟁강도": comp})
        time.sleep(0.3)

    df_final = pd.DataFrame(final_results)
    df_sorted = df_final.sort_values(by=list(("경쟁강도", "검색량")), ascending=(True, False))
    df_sorted.to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
    print("✅ 분석 완료! daily_golden_keywords.csv 파일이 생성되었습니다.")