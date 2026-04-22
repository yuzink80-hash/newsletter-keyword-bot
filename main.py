import time
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st

# 0. 스트림릿 화면 설정
st.set_page_config(page_title="황금키워드 분석기", page_icon="📈", layout="wide")

# ==========================================
# 🎨 커스텀 CSS (화면 디자인 꾸미기)
# ==========================================
st.markdown("""
<style>
    /* 입력창 주변에 은은한 네온 민트색 빛 번짐 효과 */
    div[data-baseweb="input"] > div {
        background-color: #ffffff;
        border-radius: 8px;
        box-shadow: 0 0 15px rgba(0, 255, 150, 0.2);
        border: 1px solid rgba(0, 255, 150, 0.4);
    }
    
    /* 해시태그 디자인 */
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
    
    /* 상단 안내 문구 폰트 색상 */
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

@st.cache_data(ttl=600) # 트렌드 데이터는 10분간 캐시(저장)하여 로딩 속도 향상
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

# 1. 레퍼런스 스타일의 검색창 배열 (드롭다운 + 텍스트 입력창)
col1, col2 = st.columns([1, 6])
with col1:
    search_engine = st.selectbox("엔진", ["NAVER", "GOOGLE"], label_visibility="collapsed")
with col2:
    user_keyword = st.text_input("검색어", placeholder="분석할 키워드를 입력하세요 (예: 테슬라, 미국주식)", label_visibility="collapsed")

# 2. 실시간 급상승 트렌드를 가로형 해시태그로 배치
current_trends = get_google_trends()
if current_trends:
    # 상위 5개의 트렌드만 뽑아서 해시태그 HTML 생성
    tags_html = "".join([f'<span class="trend-tag">#{kw}</span>' for kw in current_trends[:6]])
    st.markdown(tags_html + '<span class="trend-tag" style="background:none; color:#00FF96;">트렌드 더 보기 →</span>', unsafe_allow_html=True)

# 3. 분석 시작 버튼 및 로직
if st.button("분석 시작하기", type="primary", use_container_width=True):
    seeds = []
    if user_keyword.strip():
        seeds = [k.strip() for k in user_keyword.split(",") if k.strip()]
    else:
        seeds = current_trends
        
    if seeds:
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
            df_sorted = df_final.sort_values(by=["경쟁강도", "월간검색량"], ascending=[True, False])
            
            st.subheader(f"✨ 분석 완료! (총 {len(df_sorted)}개)")
            st.dataframe(df_sorted, use_container_width=True)
        else:
            st.warning("분석할 데이터를 찾지 못했습니다.")
    else:
        st.error("데이터를 수집할 수 없습니다.")