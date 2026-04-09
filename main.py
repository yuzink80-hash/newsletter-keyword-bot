import time
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import os

# 1. 시스템 환경 변수 (GitHub Secrets) 불러오기
AD_API_KEY = os.environ.get("0100000000da393051bc0ad52c63ef41b601b7fcce544c88645d22f4c40cd79d77e8e0d097").strip()
AD_SECRET_KEY = os.environ.get("AQAAAADHv6i7xheOLlXkWUe0dEuS+BOXWrp8ukJA7MPaYdqUXw==").strip()
AD_CUSTOMER_ID = os.environ.get("4348120").strip()
OPEN_CLIENT_ID = os.environ.get("P5roEfkWrGN1EJ85ifkh").strip()
OPEN_CLIENT_SECRET = os.environ.get("GFGZuG1x12").strip()

def get_google_trends():
    """오늘의 구글 실시간 트렌드 키워드 수집"""
    url = "https://trends.google.com/trending/rss?geo=KR"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            seeds = [item.find('title').text for item in root.findall('.//item')]
            print(f"📈 구글 트렌드에서 {len(seeds)}개의 키워드를 찾았습니다.")
            return seeds
    except Exception as e:
        print(f"🚨 구글 트렌드 수집 실패: {e}")
    return []

def get_naver_rel_keywords(seeds):
    """네이버 광고 API를 사용하여 연관 키워드와 검색량 가져오기"""
    if not seeds:
        return []
    
    # 상위 5개 키워드로 연관어 확장
    hint_str = ",".join(seeds[:5]).replace(" ", "")
    print(f"🔎 네이버 API 호출 시도 중... (검색어: {hint_str})")
    
    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    method = "GET"
    timestamp = str(round(time.time() * 1000))
    
    # 서명(Signature) 생성
    message = timestamp + "." + method + "." + uri
    try:
        hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
        signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
        
        headers = {
            "X-Timestamp": timestamp, 
            "X-API-KEY": AD_API_KEY, 
            "X-Customer": str(AD_CUSTOMER_ID), 
            "X-Signature": signature
        }
        params = {"hintKeywords": hint_str, "showDetail": 1}
        
        response = requests.get(base_url + uri, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            raw_list = data.get('keywordList', [])
            print(f"✅ 네이버 연관 키워드 {len(raw_list)}개 수집 성공!")
            
            result = []
            for item in raw_list:
                pc = int(item.get('monthlyPcQcCnt', 0)) if str(item.get('monthlyPcQcCnt')).isdigit() else 10
                mo = int(item.get('monthlyMobileQcCnt', 0)) if str(item.get('monthlyMobileQcCnt')).isdigit() else 10
                result.append({"keyword": item.get('relKeyword'), "volume": pc + mo})
            return result
        else:
            print(f"❌ 네이버 API 호출 실패! (상태 코드: {response.status_code})")
            print(f"에러 메시지: {response.text}")
            return []
            
    except Exception as e:
        print(f"🚨 API 처리 중 시스템 오류 발생: {e}")
        return []

def get_blog_doc_count(keyword):
    """네이버 블로그 검색 API로 발행 문서 수 조회"""
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": OPEN_CLIENT_ID, 
        "X-Naver-Client-Secret": OPEN_CLIENT_SECRET
    }
    params = {"query": keyword, "display": 1}
    try:
        res = requests.get(url, params=params, headers=headers)
        if res.status_code == 200:
            return res.json().get('total', 0)
    except:
        pass
    return 0

if __name__ == "__main__":
    print("🚀 황금키워드 자동 분석기 가동 시작!")
    
    # 1. 구글 트렌드 가져오기
    seeds = get_google_trends()
    
    # 2. 네이버 연관 검색어 확장
    raw_keywords = get_naver_rel_keywords(seeds)
    
    if raw_keywords:
        df_raw = pd.DataFrame(raw_keywords)
        # 검색량 상위 50개만 추출
        df_top50 = df_raw.sort_values(by="volume", ascending=False).head(50)
        
        final_results = []
        print("📊 키워드별 경쟁 강도 분석 중 (문서수 조회)...")
        
        for item in df_top50.to_dict('records'):
            kw, vol = item['keyword'], item['volume']
            doc = get_blog_doc_count(kw)
            # 경쟁강도 = 문서수 / 검색량
            comp = round(doc / vol, 2) if vol > 0 else 0
            final_results.append({
                "키워드": kw, 
                "월간검색량": vol, 
                "블로그문서수": doc, 
                "경쟁강도": comp
            })
            time.sleep(0.1) # 네이버 API 보호를 위한 미세 지연
            
        # 3. 결과 정렬 및 저장 (경쟁강도 낮고 검색량 높은 순)
        df_final = pd.DataFrame(final_results)
        df_sorted = df_final.sort_values(by=["경쟁강도", "월간검색량"], ascending=[True, False])
        
        df_sorted.to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
        print(f"✨ 분석 완료! {len(df_sorted)}개의 키워드가 저장되었습니다.")
    else:
        print("🚨 분석할 데이터를 찾지 못했습니다. 로그를 확인하여 API 설정을 체크해 주세요.")
        # 빈 파일이라도 생성하여 워크플로우 에러 방지
        pd.DataFrame(columns=["키워드", "월간검색량", "블로그문서수", "경쟁강도"]).to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
