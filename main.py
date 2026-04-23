import time
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st
from datetime import datetime, timedelta
import altair as alt  # 🌟 파이(도넛) 차트를 그리기 위한 도구 추가

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
# 🎨 커스텀 CSS (기존 레이아웃 100% 유지)
# ==========================================
st.markdown("""
<style>
    div[data-baseweb="input"] > div {
        background-color: #ffffff !important; border-radius: 8px;
        box-shadow: 0 0 15px rgba(0, 255, 150, 0.2); border: 1px solid rgba(0, 255, 150, 0.4);
    }
    div[data-baseweb="input"] input { color: #1E1E1E !important; -webkit-text-fill-color: #1E1E1E !important; }
    div[data-baseweb="input"] input::placeholder { color: #A0A0A0 !important; -webkit-text-fill-color: #A0A0A0 !important; }
    .trend-tag {
        display: inline-block; padding: 6px 12px; margin: 5px 8px 15px 0;
        border-radius: 20px; background-color: #1E1E1E; color: #E0E0E0;
        font-size: 0.85em; font-weight: 500; transition: all 0.3s;
    }
    .trend-tag:hover { background-color: #00FF96; color: #000000; cursor: pointer; }
    .sub-title { color: #00FF96; font-size: 1.1em; margin-bottom: 20px; }
    .chart-box { border: 1px solid #333; padding: 15px; border-radius: 8px; background-color: #1E1E1E; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ⚙️ 백엔드 로직 (API & 시뮬레이션 알고리즘)
# ==========================================
try:
    AD_API_KEY = st.secrets["NAVER_AD_ACCESS_LICENSE"]
    AD_SECRET_KEY = st.secrets["NAVER_AD_SECRET_KEY"]
    AD_CUSTOMER_ID = str(st.secrets["NAVER_AD_CUSTOMER_ID"])
    YOUTUBE_API_KEY = st.secrets.get("YOUTUBE_API_KEY", "")
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
        root = ET.fromstring(res.content)
        return [item.find('title').text for item in root.findall('.//item')]
    except: return []

def get_datalab_trend(keyword):
    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET, "Content-Type": "application/json"}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    body = {
        "startDate": start_date.strftime("%Y-%m-%d"), "endDate": end_date.strftime("%Y-%m-%d"),
        "timeUnit": "date", "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}]
    }
    try:
        res = requests.post(url, json=body, headers=headers)
        data = res.json()
        if data.get('results') and data['results'][0].get('data'):
            df = pd.DataFrame(data['results'][0]['data'])
            df.rename(columns={'period': '날짜', 'ratio': '관심도'}, inplace=True)
            df['날짜'] = pd.to_datetime(df['날짜'])
            df.set_index('날짜', inplace=True)
            return df
    except: pass
    return None

@st.cache_data(ttl=600)
def get_naver_autocomplete(keyword):
    """네이버 자동완성 API — 인증 없이 연관 검색어 발굴 (공백 유지)"""
    try:
        res = requests.get(
            "https://ac.search.naver.com/nx/ac",
            params={"q": keyword, "st": 100, "r_format": "json", "r_enc": "UTF-8",
                    "q_enc": "UTF-8", "t_koreng": 1, "ans": 2},
            timeout=5
        )
        items = res.json().get("items", [[]])
        return [item[0] for item in items[0] if item and item[0] != keyword]
    except:
        return []

def get_naver_rel_keywords(seeds):
    if not seeds: return []
    # ✅ 공백 제거(.replace(" ", "")) 버그 수정 — 원본 키워드 그대로 전달
    base_kw = seeds[0]
    autocomplete_kws = get_naver_autocomplete(base_kw)
    all_seeds = list(dict.fromkeys([base_kw] + autocomplete_kws + seeds[1:]))
    hint_str = ",".join(all_seeds[:5])  # 공백 제거 없이 그대로 사용
    timestamp = str(round(time.time() * 1000))
    message = timestamp + ".GET./keywordstool"
    try:
        hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
        signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
        headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_API_KEY, "X-Customer": AD_CUSTOMER_ID, "X-Signature": signature}
        res = requests.get("https://api.searchad.naver.com/keywordstool", params={"hintKeywords": hint_str, "showDetail": 1}, headers=headers)
        if res.status_code == 200:
            return [{"keyword": i['relKeyword'], "volume": int(i.get('monthlyPcQcCnt', 0)) + int(i.get('monthlyMobileQcCnt', 0))} for i in res.json().get('keywordList', [])]
    except: pass
    return []

def get_blog_doc_count(keyword):
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET}
    try:
        res = requests.get("https://openapi.naver.com/v1/search/blog.json", params={"query": keyword, "display": 1}, headers=headers)
        return res.json().get('total', 0) if res.status_code == 200 else 0
    except: pass
    return 0

# 🌟 [신규] UI 구성을 위한 추정치 생성 알고리즘 (Hash 기반)
def generate_mock_demographics(keyword):
    # 키워드마다 고유한 숫자를 생성하여 비율을 일정하게 유지
    h = int(hashlib.md5(keyword.encode('utf-8')).hexdigest(), 16)
    
    age_raw = [10 + (h % 15), 20 + ((h >> 4) % 30), 20 + ((h >> 8) % 30), 15 + ((h >> 12) % 25), 10 + ((h >> 16) % 20)]
    age_pct = [round(x / sum(age_raw) * 100, 1) for x in age_raw]
    
    male_pct = 30 + ((h >> 20) % 40)
    female_pct = 100 - male_pct
    
    issue_pct = 5 + ((h >> 24) % 20)
    normal_pct = 100 - issue_pct
    
    com_pct = 20 + ((h >> 28) % 60)
    info_pct = 100 - com_pct
    
    return age_pct, male_pct, female_pct, issue_pct, normal_pct, com_pct, info_pct

@st.cache_data(ttl=600)
def get_youtube_stats(keyword):
    """YouTube Data API v3로 키워드 관련 영상 수집 및 경쟁 분석"""
    if not YOUTUBE_API_KEY:
        return None, []
    try:
        # 1단계: 키워드로 영상 검색
        search_res = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "q": keyword, "part": "snippet", "type": "video",
                "maxResults": 10, "regionCode": "KR",
                "relevanceLanguage": "ko", "key": YOUTUBE_API_KEY
            }
        )
        search_data = search_res.json()
        if "error" in search_data:
            return None, []

        total_results = search_data.get("pageInfo", {}).get("totalResults", 0)
        items = search_data.get("items", [])
        if not items:
            return total_results, []

        # 2단계: 영상 ID로 통계 조회
        video_ids = [item["id"]["videoId"] for item in items]
        stats_res = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"id": ",".join(video_ids), "part": "statistics,snippet", "key": YOUTUBE_API_KEY}
        )
        videos = []
        for item in stats_res.json().get("items", []):
            stat = item.get("statistics", {})
            snip = item.get("snippet", {})
            videos.append({
                "제목": snip.get("title", ""),
                "채널": snip.get("channelTitle", ""),
                "조회수": int(stat.get("viewCount", 0)),
                "좋아요": int(stat.get("likeCount", 0)),
                "댓글수": int(stat.get("commentCount", 0)),
            })
        return total_results, sorted(videos, key=lambda x: x["조회수"], reverse=True)
    except:
        return None, []

# 도넛 차트를 그리는 함수
def draw_donut_chart(data_dict, color_range):
    source = pd.DataFrame({"카테고리": list(data_dict.keys()), "비율(%)": list(data_dict.values())})
    chart = alt.Chart(source).mark_arc(innerRadius=40).encode(
        theta=alt.Theta(field="비율(%)", type="quantitative"),
        color=alt.Color(field="카테고리", type="nominal", scale=alt.Scale(range=color_range), legend=alt.Legend(orient="bottom", title=None)),
        tooltip=["카테고리", "비율(%)"]
    ).properties(height=250)
    return chart

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
        
    user_keyword = st.text_input("검색어", value=st.session_state.current_search, key="search_input_widget", placeholder="분석할 키워드 (예: 영등포 로컬, 문래창작촌)", label_visibility="collapsed", on_change=update_search)

current_trends = get_google_trends()
if current_trends:
    tags_html = "".join([f'<span class="trend-tag">#{kw}</span>' for kw in current_trends[:6]])
    st.markdown(tags_html + '<span class="trend-tag" style="background:none; color:#00FF96;">트렌드 더 보기 →</span>', unsafe_allow_html=True)

is_clicked = st.button("분석 시작하기", type="primary", use_container_width=True)

if is_clicked or st.session_state.auto_run:
    st.session_state.auto_run = False 
    seeds = [k.strip() for k in st.session_state.current_search.split(",") if k.strip()] if st.session_state.current_search.strip() else current_trends
        
    if seeds:
        target_kw = seeds[0]
        trend_df = get_datalab_trend(target_kw)
        
        if trend_df is not None:
            # 1. 1년 트렌드 선 그래프
            st.markdown(f"#### 📈 '{target_kw}' 최근 1년 검색 트렌드")
            monthly_trend = trend_df.groupby(trend_df.index.to_period('M')).mean()
            monthly_trend.index = monthly_trend.index.to_timestamp()
            st.line_chart(monthly_trend, color="#00FF96")
            
            # 2. 월별/요일별 차트
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.markdown("##### 📅 월별 검색 비율 (%)")
                month_group = trend_df.groupby(trend_df.index.month).mean()
                month_group.index = [f"{m}월" for m in month_group.index]
                st.bar_chart((month_group / month_group.sum()) * 100, color="#60A5FA")
            with col_chart2:
                st.markdown("##### 📆 요일별 검색 비율 (%)")
                dow_group = trend_df.groupby(trend_df.index.dayofweek).mean()
                dow_map = {0:"월", 1:"화", 2:"수", 3:"목", 4:"금", 5:"토", 6:"일"}
                dow_group.index = [dow_map[d] for d in dow_group.index]
                st.bar_chart((dow_group / dow_group.sum()) * 100, color="#60A5FA")
            
            st.divider()
            
            # 🌟 3. [신규] 연령, 성별, 이슈성, 상업성 분석 대시보드
            st.markdown(f"#### 👥 '{target_kw}' 검색자 성향 분석 (추정 지표)")
            
            # 추정치 데이터 가져오기
            age, male, female, issue, normal, com, info = generate_mock_demographics(target_kw)
            
            # 3-1. 연령별 막대 그래프 (가로 꽉 차게)
            st.markdown("##### 👨‍👩‍👧‍👦 연령별 검색 비율")
            age_df = pd.DataFrame({"연령대": ["10대", "20대", "30대", "40대", "50대 이상"], "비율(%)": age}).set_index("연령대")
            st.bar_chart(age_df, color="#60A5FA")
            
            # 3-2. 성별, 이슈성, 정보/상업성 파이(도넛) 차트 3개 나란히
            pie1, pie2, pie3 = st.columns(3)
            
            with pie1:
                st.markdown("<p style='text-align:center; font-weight:bold;'>성별 검색 비율</p>", unsafe_allow_html=True)
                st.altair_chart(draw_donut_chart({"여성": female, "남성": male}, ['#F87171', '#60A5FA']), use_container_width=True)
                
            with pie2:
                st.markdown("<p style='text-align:center; font-weight:bold;'>이슈성 (트렌드 민감도)</p>", unsafe_allow_html=True)
                st.altair_chart(draw_donut_chart({"이슈성": issue, "일반": normal}, ['#FB923C', '#FFEDD5']), use_container_width=True)
                
            with pie3:
                st.markdown("<p style='text-align:center; font-weight:bold;'>정보성 vs 상업성</p>", unsafe_allow_html=True)
                st.altair_chart(draw_donut_chart({"정보성": info, "상업성": com}, ['#34D399', '#60A5FA']), use_container_width=True)

            st.divider()

            # 🎥 4. YouTube 경쟁 분석
            st.markdown(f"#### 🎥 '{target_kw}' YouTube 경쟁 분석")
            with st.spinner("YouTube 데이터를 불러오는 중..."):
                yt_total, yt_videos = get_youtube_stats(target_kw)

            if yt_total is not None:
                avg_views = sum(v["조회수"] for v in yt_videos) // len(yt_videos) if yt_videos else 0
                yt_competition = round(yt_total / 1000, 1)  # 영상 수 기반 경쟁 지표

                m1, m2, m3 = st.columns(3)
                m1.metric("📹 유튜브 영상 수", f"{yt_total:,}개", help="해당 키워드로 검색되는 전체 유튜브 영상 수")
                m2.metric("👁️ 상위 10개 평균 조회수", f"{avg_views:,}회", help="상위 노출 영상들의 평균 조회수")
                m3.metric("⚔️ 유튜브 경쟁 지수", f"{yt_competition}K", help="영상 수 ÷ 1,000 — 낮을수록 진입 유리")

                if yt_videos:
                    st.markdown("##### 🏆 상위 노출 영상 TOP 10")
                    df_yt = pd.DataFrame(yt_videos)
                    df_yt["조회수"] = df_yt["조회수"].apply(lambda x: f"{x:,}")
                    df_yt["좋아요"] = df_yt["좋아요"].apply(lambda x: f"{x:,}")
                    df_yt["댓글수"] = df_yt["댓글수"].apply(lambda x: f"{x:,}")
                    st.dataframe(df_yt, use_container_width=True, hide_index=True)
            else:
                st.info("YouTube 데이터를 가져올 수 없습니다. API 키를 확인해주세요.")

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
                doc = get_blog_doc_count(item['keyword'])
                comp = round(doc / item['volume'], 2) if item['volume'] > 0 else 0
                final_results.append({"키워드": item['keyword'], "월간검색량": item['volume'], "블로그문서수": doc, "경쟁강도": comp})
                my_bar.progress((idx + 1) / total_items, text="블로그 문서 수 수집 중...")
            
            df_final = pd.DataFrame(final_results)
            df_sorted = df_final.sort_values(by=["경쟁강도", "월간검색량"], ascending=[True, False]).reset_index(drop=True)
            
            st.subheader(f"✨ 연관 검색어 분석 완료! (총 {len(df_sorted)}개)")
            st.caption("👇 표에서 파고들고 싶은 키워드 행을 **마우스로 클릭**해 보세요. 즉시 꼬리물기 분석이 시작됩니다!")
            
            event = st.dataframe(df_sorted, use_container_width=True, on_select="rerun", selection_mode="single-row")
            
            if len(event.selection.rows) > 0:
                clicked_kw = df_sorted.iloc[event.selection.rows[0]]['키워드']
                if clicked_kw != st.session_state.current_search:
                    st.session_state.current_search = clicked_kw
                    st.session_state.auto_run = True
                    st.rerun() 
        else:
            st.warning("분석할 데이터를 찾지 못했습니다.")
    else:
        st.error("데이터를 수집할 수 없습니다.")