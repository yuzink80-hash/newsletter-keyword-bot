import time
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st

# 0. 스트림릿 화면 설정 (이 코드가 반드시 맨 위에 있어야 에러가 안 납니다!)
st.set_page_config(page_title="황금키워드 분석기", page_icon="📈", layout="wide")

# 1. Streamlit Secrets에서 API 키를 정확한 '이름'으로 불러옵니다.
try:
    AD_API_KEY = st.secrets["NAVER_AD_ACCESS_LICENSE"]
    AD_SECRET_KEY = st.secrets["NAVER_AD_SECRET_KEY"]
    AD_CUSTOMER_ID = str(st.secrets["NAVER_AD_CUSTOMER_ID"])
except KeyError:
    st.error("오른쪽 아래 Manage app -> Settings -> Secrets에 네이버 API 키를 먼저 넣어주세요!")
    st.stop()

# 블로그 API (임시)
OPEN_CLIENT_ID = "P5roEfkWrGN1EJ85ifkh"
OPEN_CLIENT_SECRET = "GFGZuG1x12"

def get_google_trends():
    """오늘의 구글 실시간 트렌드 키워드 수집"""
    url = "https://trends.google.com/trending/rss?geo=KR"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            seeds = [item.find('title').text for item in root.findall('.//item')]
            return seeds
    except Exception as e:
        st.error(f"🚨 구글 트렌드 수집 실패: {e}")
    return []

def get_naver_rel_keywords(seeds):
    """네이버 광고 API를 사용하여 연관 키워드와 검색량 가져오기"""
    if not seeds:
        return []
    
    hint_str = ",".join(seeds[:5]).replace(" ", "")
    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    method = "GET"
    timestamp = str(round(time.time() * 1000))
    
    message = timestamp + "." + method + "." + uri
    try:
        hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
        signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
        
        headers = {
            "X-Timestamp": timestamp, 
            "X-API-KEY": AD_API_KEY, 
            "X-Customer": AD_CUSTOMER_ID, 
            "X-Signature": signature
        }
        params = {"hintKeywords": hint_str, "showDetail": 1}
        
        response = requests.get(base_url + uri, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            raw_list = data.get('keywordList', [])
            
            result = []
            for item in raw_list:
                pc = int(item.get('monthlyPcQcCnt', 0)) if str(item.get('monthlyPcQcCnt')).isdigit() else 10
                mo = int(item.get('monthlyMobileQcCnt', 0)) if str(item.get('monthlyMobileQcCnt')).isdigit() else 10
                result.append({"keyword": item.get('relKeyword'), "volume": pc + mo})
            return result
        else:
            st.error(f"❌ 네이버 API 호출 실패! (상태 코드: {response.status_code})")
            st.code(response.text)
            return []
            
    except Exception as e:
        st.error(f"🚨 API 처리 중 오류 발생: {e}")
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

# UI 부분
st.title("🚀 황금키워드 자동 분석기")
st.write("원하는 키워드를 직접 검색하거나, 구글 실시간 트렌드를 기반으로 최적의 네이버 연관 검색어를 찾습니다.")

user_keyword = st.text_input(
    "🔍 분석하고 싶은 핵심 키워드를 입력하세요", 
    placeholder="예: 영등포 로컬, 캠핑장, 미국주식 (비워두면 구글 실시간 트렌드로 자동 분석합니다)"
)

if st.button("분석 시작하기", type="primary"):
    seeds = []
    
    if user_keyword.strip():
        seeds = [user_keyword.strip()]
        st.success(f"🎯 '{user_keyword}' 키워드를 바탕으로 네이버 연관 검색어를 확장합니다.")
    else:
        with st.spinner("구글 트렌드 실시간 키워드를 수집하고 있습니다..."):
            seeds = get_google_trends()
        if seeds:
            st.success(f"📈 구글 트렌드에서 {len(seeds)}개의 키워드를 찾았습니다.")
    
    if seeds:
        with st.spinner("네이버 연관 검색어와 검색량을 분석 중입니다..."):
            raw_keywords = get_naver_rel_keywords(seeds)
        
        if raw_keywords:
            df_raw = pd.DataFrame(raw_keywords)
            df_top50 = df_raw.sort_values(by="volume", ascending=False).head(50)
            
            final_results = []
            
            progress_text = "경쟁 강도(블로그 문서 수)를 분석 중입니다..."
            my_bar = st.progress(0, text=progress_text)
            
            total_items = len(df_top50)
            for idx, item in enumerate(df_top50.to_dict('records')):
                kw, vol = item['keyword'], item['volume']
                doc = get_blog_doc_count(kw)
                comp = round(doc / vol, 2) if vol > 0 else 0
                final_results.append({
                    "키워드": kw, 
                    "월간검색량": vol, 
                    "블로그문서수": doc, 
                    "경쟁강도": comp
                })
                time.sleep(0.1)
                my_bar.progress((idx + 1) / total_items, text=progress_text)
            
            df_final = pd.DataFrame(final_results)
            df_sorted = df_final.sort_values(by=["경쟁강도", "월간검색량"], ascending=[True, False])
            
            df_sorted.to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
            st.subheader(f"✨ 분석 완료! (총 {len(df_sorted)}개)")
            st.dataframe(df_sorted, use_container_width=True)
        else:
            st.warning("분석할 데이터를 찾지 못했습니다.")
    else:
        st.error("분석을 시작할 기초 키워드를 찾지 못했습니다.")