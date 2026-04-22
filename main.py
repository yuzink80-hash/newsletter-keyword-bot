import time
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st

# 0. 화면 설정
st.set_page_config(page_title="황금키워드 데이터랩", page_icon="📈", layout="wide")

# 🧠 기억 상자 (세션 상태) 초기화
if 'current_search' not in st.session_state:
    st.session_state.current_search = ""
if 'search_history' not in st.session_state:
    st.session_state.search_history = []
if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False

# 🎨 디자인 (민트 네온 효과)
st.markdown("""
<style>
    div[data-baseweb="input"] > div {
        background-color: #ffffff !important; border-radius: 8px;
        box-shadow: 0 0 15px rgba(0, 255, 150, 0.2);
        border: 1px solid rgba(0, 255, 150, 0.4);
    }
    div[data-baseweb="input"] input { color: #1E1E1E !important; -webkit-text-fill-color: #1E1E1E !important; }
    div[data-baseweb="input"] input::placeholder { color: #A0A0A0 !important; }
    .trend-tag {
        display: inline-block; padding: 6px 12px; margin: 5px 8px;
        border-radius: 20px; background-color: #1E1E1E; color: #E0E0E0;
        font-size: 0.85em; transition: all 0.3s;
    }
    .breadcrumb { color: #00FF96; font-size: 0.9em; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- [API 로직 생략: 이전과 동일] ---
try:
    AD_API_KEY = st.secrets["NAVER_AD_ACCESS_LICENSE"]
    AD_SECRET_KEY = st.secrets["NAVER_AD_SECRET_KEY"]
    AD_CUSTOMER_ID = str(st.secrets["NAVER_AD_CUSTOMER_ID"])
except:
    st.error("Secrets 설정을 확인해주세요."); st.stop()

OPEN_CLIENT_ID = "P5roEfkWrGN1EJ85ifkh"
OPEN_CLIENT_SECRET = "GFGZuG1x12"

@st.cache_data(ttl=600)
def get_google_trends():
    url = "https://trends.google.com/trending/rss?geo=KR"
    try:
        res = requests.get(url, timeout=10)
        root = ET.fromstring(res.content)
        return [item.find('title').text for item in root.findall('.//item')]
    except: return []

def get_naver_rel_keywords(seeds):
    hint_str = ",".join(seeds[:5]).replace(" ", "")
    timestamp = str(round(time.time() * 1000))
    message = timestamp + ".GET./keywordstool"
    hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
    signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
    headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_API_KEY, "X-Customer": AD_CUSTOMER_ID, "X-Signature": signature}
    res = requests.get("https://api.searchad.naver.com/keywordstool", params={"hintKeywords": hint_str, "showDetail": 1}, headers=headers)
    if res.status_code == 200:
        return [{"keyword": i['relKeyword'], "volume": int(i.get('monthlyPcQcCnt', 10))+int(i.get('monthlyMobileQcCnt', 10))} for i in res.json().get('keywordList', [])]
    return []

def get_blog_doc_count(kw):
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET}
    res = requests.get("https://openapi.naver.com/v1/search/blog.json", params={"query": kw, "display": 1}, headers=headers)
    return res.json().get('total', 0) if res.status_code == 200 else 0

# --- [UI 메인 창] ---
st.title("🚀 황금키워드 데이터랩")

# 탐색 경로 표시
if st.session_state.search_history:
    st.markdown(f'<div class="breadcrumb">탐색 경로: {" > ".join(st.session_state.search_history[-5:])}</div>', unsafe_allow_html=True)

user_keyword = st.text_input("검색어", value=st.session_state.current_search, placeholder="분석할 키워드 입력 (예: 가죽 공예, 지속가능성)", label_visibility="collapsed")

if st.button("분석 시작하기", type="primary", use_container_width=True) or st.session_state.auto_run:
    st.session_state.auto_run = False
    seeds = [k.strip() for k in user_keyword.split(",") if k.strip()] if user_keyword else get_google_trends()
    
    if seeds:
        # 히스토리에 추가
        if seeds[0] not in st.session_state.search_history:
            st.session_state.search_history.append(seeds[0])
            
        with st.spinner(f"'{seeds[0]}' 기반 연관어 분석 중..."):
            raw_data = get_naver_rel_keywords(seeds)
            if raw_data:
                df = pd.DataFrame(raw_data).sort_values(by="volume", ascending=False).head(30).reset_index(drop=True)
                results = []
                bar = st.progress(0, text="경쟁 강도 측정 중...")
                for idx, row in enumerate(df.to_dict('records')):
                    doc = get_blog_doc_count(row['keyword'])
                    comp = round(doc / row['volume'], 2) if row['volume'] > 0 else 0
                    results.append({"키워드": row['keyword'], "검색량": row['volume'], "문서수": doc, "경쟁강도": comp})
                    bar.progress((idx+1)/len(df))
                
                final_df = pd.DataFrame(results).sort_values(by="경쟁강도")
                st.subheader("✨ 분석 완료")
                st.info("💡 아래 표에서 파고들고 싶은 키워드 줄을 클릭하면 즉시 재분석합니다.")
                
                # 상호작용형 데이터프레임
                event = st.dataframe(final_df, use_container_width=True, on_select="rerun", selection_mode="single-row")
                
                if len(event.selection.rows) > 0:
                    selected_kw = final_df.iloc[event.selection.rows[0]]['키워드']
                    if selected_kw != st.session_state.current_search:
                        st.session_state.current_search = selected_kw
                        st.session_state.auto_run = True
                        st.rerun()