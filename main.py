import time
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st
from datetime import datetime, timedelta

# 0. 스트림릿 화면 설정
st.set_page_config(page_title="황금키워드 데이터랩", page_icon="📈", layout="wide")

# ==========================================
# 🧠 세션 상태 (기억 상자) 초기화
# ==========================================
if 'current_search' not in st.session_state:
    st.session_state.current_search = ""
if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False

# ==========================================
# 🎨 커스텀 CSS (기존 레이아웃 100% 유지!)
# ==========================================
st.markdown("""
<style>
    div[data-baseweb="input"] > div {
        background-color: #ffffff !important;
        border-radius: 8px;
        box-shadow: 0 0 15px rgba(0, 255, 150, 0.2);
        border: 1px solid rgba(0, 255, 150, 0.4);
    }
    div[data-baseweb="input"] input {
        color: #1E1E1E !important;
        -webkit-text-fill-color: #1E1E1E !important;
    }
    div[data-baseweb="input"] input::placeholder {
        color: #A0A0A0 !important;
        -webkit-text-fill-color: #A0A0A0 !important;
    }
    .trend-tag {
        display: inline-block;
        padding: 6px 12px;
        margin: 5px 8px 15px 0;
        border-radius: 20px;
        background-color: #1E1E1E;
        color: #E0E0E0;
        font-size: 0.85em;
        font-weight: 500;
        transition: all 0.3s;
    }
    .trend-tag:hover {
        background-color: #00FF96;
        color: #000000;
        cursor: pointer;
    }
    .sub-title {
        color: #00FF96;
        font-size: 1.1em;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 백엔드 로직 (데이터 수집 엔진)
# ==========================================
try:
    AD_API_KEY = st.secrets["NAVER_AD_ACCESS_LICENSE"]
    AD_SECRET_KEY = st.secrets["NAVER_AD_SECRET_KEY"]
    AD_CUSTOMER_ID = str(st.secrets["NAVER_AD_CUSTOMER_ID"])
except KeyError:
    st.error("오른쪽 아래 Manage app -> Settings -> Secrets에 네이버 API 키를 먼저 넣어주세요!")
    st.stop()

OPEN_CLIENT_ID = "P5roEfkWrGN1EJ85ifkh"
OPEN_CLIENT_SECRET = "GFGZuG1x12"

@st.cache_data(ttl=600)
def get_google_trends():
    url = "https://trends.google.com/trending/rss?geo=KR"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            return [item.find('title').text for item in root.findall('.//item')]
    except:
        pass
    return []

def get_datalab_trend(keyword):
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id": OPEN_CLIENT_ID,
        "X-Naver-Client-Secret": OPEN_CLIENT_SECRET,
        "Content-Type": "application/json"
    }
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date",  # 🌟 일간 데이터로 쪼개서 가져옵니다.
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]
    }
    
    try:
        res = requests.post(url, json=body, headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data.get('results') and data['results'][0].get('data'):
                df = pd.DataFrame(data['results'][0]['data'])
                df.rename(columns={'period': '날짜', 'ratio': '관심도'}, inplace=True)
                df['날짜'] = pd.to_datetime(df['날짜'])
                df.set_index('날짜', inplace=True)
                return df
    except Exception as e:
        pass
    return None

def get_naver_rel_keywords(seeds):
    if not seeds:
        return []
    hint_str = ",".join(seeds[:5]).replace(" ", "")
    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    timestamp = str(round(time.time() * 1000))
    message = timestamp + ".GET." + uri
    try:
        hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
        signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
        headers = {
            "X-Timestamp": timestamp, "X-API-KEY": AD_API_KEY, 
            "X-Customer": AD_CUSTOMER_ID, "X-Signature": signature
        }
        res = requests.get(base_url + uri, params={"hintKeywords": hint_str, "showDetail": 1}, headers=headers)
        if res.status_code == 200:
            raw_list = res.json().get('keywordList', [])
            result = []
            for item in raw_list:
                pc = int(item.get('monthlyPcQcCnt', 0)) if str(item.get('monthlyPcQcCnt')).isdigit() else 10
                mo = int(item.get('monthlyMobileQcCnt', 0)) if str(item.get('monthlyMobileQcCnt')).isdigit() else 10
                result.append({"keyword": item.get('relKeyword'), "volume": pc + mo})
            return result
    except:
        pass
    return []

def get_blog_doc_count(keyword):
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET}
    try:
        res = requests.get(url, params={"query": keyword, "display": 1}, headers=headers)
        if res.status_code == 200:
            return res.json().get('total', 0)
    except:
        pass
    return 0


# ==========================================
# 🖥️ 프론트엔드 UI (화면 그리기)
# ==========================================
st.title("🚀 황금키워드 데이터랩")
st.markdown('<p class="sub-title">키워드 데이터 분석을 통해 콘텐츠의 유입률을 늘리고, 비즈니스를 확장시켜보세요.</p>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 6])
with col1:
    search_engine = st.selectbox("엔진", ["NAVER", "GOOGLE"], label_visibility="collapsed")
with col2:
    def update_search():
        st.session_state.current_search = st.session_state.search_input_widget
        st.session_state.auto_run = False
        
    user_keyword = st.text_input(
        "검색어", 
        value=st.session_state.current_search,
        key="search_input_widget",
        placeholder="분석할 키워드를 입력하세요 (예: 문래창작촌, 영등포 로컬)", 
        label_visibility="collapsed",
        on_change=update_search
    )

current_trends = get_google_trends()
if current_trends:
    tags_html = "".join([f'<span class="trend-tag">#{kw}</span>' for kw in current_trends[:6]])
    st.markdown(tags_html + '<span class="trend-tag" style="background:none; color:#00FF96;">트렌드 더 보기 →</span>', unsafe_allow_html=True)

is_clicked = st.button("분석 시작하기", type="primary", use_container_width=True)

if is_clicked or st.session_state.auto_run:
    st.session_state.auto_run = False 
    
    seeds = []
    actual_keyword = st.session_state.current_search
    
    if actual_keyword.strip():
        seeds = [k.strip() for k in actual_keyword.split(",") if k.strip()]
    else:
        seeds = current_trends
        
    if seeds:
        trend_df = get_datalab_trend(seeds[0])
        if trend_df is not None:
            # 1. 1년 트렌드 꺾은선 그래프
            st.markdown(f"#### 📈 '{seeds[0]}' 최근 1년 검색 트렌드")
            monthly_trend = trend_df.groupby(trend_df.index.to_period('M')).mean()
            monthly_trend.index = monthly_trend.index.to_timestamp()
            st.line_chart(monthly_trend, color="#00FF96")
            
            # 🌟 2. [추가된 부분] 월별 / 요일별 막대 그래프 나란히 배치
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.markdown("##### 📅 월별 검색 비율 (%)")
                month_group = trend_df.groupby(trend_df.index.month).mean()
                month_group.index = [f"{m}월" for m in month_group.index]
                month_ratio = (month_group / month_group.sum()) * 100
                st.bar_chart(month_ratio, color="#60A5FA") # 블랙키위 스타일 하늘색
                
            with col_chart2:
                st.markdown("##### 📆 요일별 검색 비율 (%)")
                dow_group = trend_df.groupby(trend_df.index.dayofweek).mean()
                dow_map = {0:"월", 1:"화", 2:"수", 3:"목", 4:"금", 5:"토", 6:"일"}
                dow_group.index = [dow_map[d] for d in dow_group.index]
                dow_ratio = (dow_group / dow_group.sum()) * 100
                st.bar_chart(dow_ratio, color="#60A5FA") # 블랙키위 스타일 하늘색
                
            st.divider() 
            
        with st.spinner("네이버 연관 검색어와 경쟁 강도를 분석 중입니다..."):
            raw_keywords = get_naver_rel_keywords(seeds)
        
        if raw_keywords:
            df_raw = pd.DataFrame(raw_keywords)
            df_top50 = df_raw.sort_values(by="volume", ascending=False).head(50)
            
            final_results = []
            my_bar = st.progress(0, text="블로그 문서 수 수집 중...")
            
            total_items = len(df_top50)
            for idx, item in enumerate(df_top50.to_dict('records')):
                kw, vol = item['keyword'], item['volume']
                doc = get_blog_doc_count(kw)
                comp = round(doc / vol, 2) if vol > 0 else 0
                final_results.append({"키워드": kw, "월간검색량": vol, "블로그문서수": doc, "경쟁강도": comp})
                my_bar.progress((idx + 1) / total_items, text="블로그 문서 수 수집 중...")
            
            df_final = pd.DataFrame(final_results)
            df_sorted = df_final.sort_values(by=["경쟁강도", "월간검색량"], ascending=[True, False]).reset_index(drop=True)
            
            st.subheader(f"✨ 분석 완료! (총 {len(df_sorted)}개)")
            st.caption("👇 표에서 파고들고 싶은 키워드 행을 **마우스로 클릭**해 보세요. 즉시 꼬리물기 분석이 시작됩니다!")
            
            event = st.dataframe(
                df_sorted, 
                use_container_width=True,
                on_select="rerun",           
                selection_mode="single-row"  
            )
            
            if len(event.selection.rows) > 0:
                selected_idx = event.selection.rows[0]
                clicked_kw = df_sorted.iloc[selected_idx]['키워드']
                
                if clicked_kw != st.session_state.current_search:
                    st.session_state.current_search = clicked_kw
                    st.session_state.auto_run = True
                    st.rerun() 
        else:
            st.warning("분석할 데이터를 찾지 못했습니다.")
    else:
        st.error("데이터를 수집할 수 없습니다.")