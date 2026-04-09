import time, requests, hashlib, hmac, base64, os
import pandas as pd
import xml.etree.ElementTree as ET

# 1. API 키 설정 (환경 변수)
keys = {
    "AD_API": os.environ.get("01000000000c940f8019a6d420411b1103413f766b201bcb73aa7f4042913af21f433b8156", ""),
    "AD_SEC": os.environ.get("AQAAAAAMlA+AGabUIEEbEQNBP3ZrNQLWfCqgpo5peoORAozOxg==", ""),
    "AD_CUS": os.environ.get("4348120", ""),
    "ID": os.environ.get("P5roEfkWrGN1EJ85ifkh", ""),
    "SEC": os.environ.get("GFGZuG1x12", "")
}

def get_google_trends():
    """오늘의 구글 핫 트렌드 수집"""
    url = "https://trends.google.com/trending/rss?geo=KR"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            seeds = [i.find('title').text for i in root.findall('.//item')]
            print(f"📈 구글 트렌드 {len(seeds)}개 발견")
            return seeds
    except Exception as e:
        print(f"🚨 구글 트렌드 수집 실패: {e}")
    return []

def get_naver_rel_keywords(seeds):
    """네이버 연관 검색어 및 검색량 수집"""
    if not seeds: return []
    
    # 상위 5개 키워드로 연관어 확장
    hint = ",".join(seeds[:5]).replace(" ", "")
    ts = str(round(time.time() * 1000))
    msg = f"{ts}.GET./keywordstool"
    
    try:
        sign = base64.b64encode(hmac.new(bytes(keys["AD_SEC"], "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()).decode("utf-8")
        headers = {"X-Timestamp": ts, "X-API-KEY": keys["AD_API"], "X-Customer": str(keys["AD_CUS"]), "X-Signature": sign}
        
        r = requests.get("https://api.searchad.naver.com/keywordstool", params={"hintKeywords": hint, "showDetail": 1}, headers=headers)
        
        if r.status_code == 200:
            data = r.json().get('keywordList', [])
            print(f"✅ 네이버 연관 검색어 {len(data)}개 수집 성공")
            return [{"keyword": i['relKeyword'], "volume": (int(i.get('monthlyPcQcCnt',0)) if str(i.get('monthlyPcQcCnt')).isdigit() else 10) + (int(i.get('monthlyMobileQcCnt',0)) if str(i.get('monthlyMobileQcCnt')).isdigit() else 10)} for i in data]
        else:
            print(f"❌ 네이버 광고 API 에러: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"🚨 네이버 API 호출 중 시스템 오류: {e}")
    return []

def get_blog_doc_count(keyword):
    """네이버 블로그 문서 수 조회"""
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {"X-Naver-Client-Id": keys["ID"], "X-Naver-Client-Secret": keys["SEC"]}
    try:
        r = requests.get(url, params={"query": keyword, "display": 1}, headers=headers)
        if r.status_code == 200:
            return r.json().get('total', 0)
    except:
        pass
    return 0

if __name__ == "__main__":
    print("🚀 황금 키워드 분석 시작...")
    
    # 1. 시드 키워드 확보
    seeds = get_google_trends()
    
    # 2. 검색량 데이터 확보
    raw_data = get_naver_rel_keywords(seeds)
    
    if raw_data:
        # 3. 상위 50개 선정 후 블로그 문서수 및 경쟁강도 계산
        df = pd.DataFrame(raw_data).sort_values(by="volume", ascending=False).head(50)
        
        final_list = []
        for item in df.to_dict('records'):
            kw, vol = item['keyword'], item['volume']
            doc = get_blog_doc_count(kw)
            comp = round(doc / vol, 2) if vol > 0 else 0
            final_list.append({"키워드": kw, "월간검색량": vol, "블로그문서수": doc, "경쟁강도": comp})
            time.sleep(0.1) # API 과부하 방지
            
        # 4. 결과 저장 (경쟁강도 낮은 순, 검색량 높은 순)
        result_df = pd.DataFrame(final_list).sort_values(by=["경쟁강도", "월간검색량"], ascending=[True, False])
        result_df.to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
        print(f"✨ 최종 황금키워드 리스트 저장 완료! ({len(result_df)}개)")
    else:
        print("🚨 분석할 데이터가 수집되지 않았습니다. API 설정을 다시 확인해 주세요.")
