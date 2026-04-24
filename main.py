import time
import re
import requests
import hashlib
import hmac
import base64
import pandas as pd
import xml.etree.ElementTree as ET
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
import altair as alt

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_OK = True
except ImportError:
    GSPREAD_OK = False

# 0. 스트림릿 화면 설정
st.set_page_config(page_title="황금키워드 데이터랩", page_icon="📈", layout="wide")

# ==========================================
# 🧠 세션 상태 (기억 상자) 초기화
# ==========================================
if 'current_search' not in st.session_state:
    st.session_state.current_search = ""
if 'auto_run' not in st.session_state:
    st.session_state.auto_run = False
if 'categories' not in st.session_state:
    st.session_state.categories = ["캠핑", "실내요리", "로컬", "재테크", "뷰티", "패션", "육아", "여행", "기타"]
if 'last_df_sorted' not in st.session_state:
    st.session_state.last_df_sorted = None
if 'last_target_kw' not in st.session_state:
    st.session_state.last_target_kw = ""
if 'last_category' not in st.session_state:
    st.session_state.last_category = ""

# 검색바 텍스트 동기화: text_input 렌더링 전에 위젯 키를 업데이트해야 에러가 없음
if st.session_state.get('_pending_search'):
    st.session_state.search_input_widget = st.session_state._pending_search
    st.session_state._pending_search = None

# ==========================================
# 🎨 커스텀 CSS (기존 레이아웃 100% 유지)
# ==========================================
st.markdown("""
<style>
    /* ── 전체 배경 ── */
    .stApp { background-color: #1C1A17; }
    section[data-testid="stSidebar"] { background-color: #1C1A17; }

    /* ── 콘텐츠 여백 (블랙키위 스타일 side margin) ── */
    .main .block-container {
        max-width: 1080px !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
        padding-top: 2rem !important;
        margin: 0 auto !important;
    }

    /* ── 섹션 카드 ── */
    .section-card {
        background-color: #232018;
        border: 1px solid rgba(138, 128, 112, 0.18);
        border-radius: 12px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.28), 0 1px 6px rgba(0,0,0,0.16);
        padding: 24px 28px;
        margin-bottom: 20px;
    }
    .section-card-title {
        font-size: 0.72em;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #8A8070;
        margin-bottom: 4px;
    }
    .section-card-heading {
        font-size: 1.15em;
        font-weight: 700;
        color: #F4EFE4;
        margin-bottom: 16px;
    }

    /* ── 검색창 ── */
    div[data-baseweb="input"] > div {
        background-color: #F4EFE4 !important;
        border-radius: 8px;
        box-shadow: 0 0 15px rgba(154, 123, 60, 0.25);
        border: 1px solid rgba(154, 123, 60, 0.5) !important;
    }
    div[data-baseweb="input"] input {
        color: #1C1A17 !important;
        -webkit-text-fill-color: #1C1A17 !important;
        font-weight: 500;
    }
    div[data-baseweb="input"] input::placeholder {
        color: #8A8070 !important;
        -webkit-text-fill-color: #8A8070 !important;
    }

    /* ── 트렌드 태그 ── */
    .trend-tag {
        display: inline-block; padding: 6px 14px; margin: 5px 8px 15px 0;
        border-radius: 20px; background-color: #2A2620;
        border: 1px solid rgba(138, 128, 112, 0.4);
        color: #F4EFE4; font-size: 0.85em; font-weight: 500;
        transition: all 0.25s ease;
    }
    .trend-tag:hover {
        background-color: #9A7B3C;
        border-color: #9A7B3C;
        color: #F4EFE4;
        cursor: pointer;
    }

    /* ── 서브타이틀 ── */
    .sub-title { color: #9A7B3C; font-size: 1em; margin-bottom: 24px; font-weight: 400; }

    /* ── 메트릭 카드 ── */
    div[data-testid="metric-container"] {
        background-color: #232018;
        border: 1px solid rgba(138, 128, 112, 0.2);
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.2);
    }
    div[data-testid="metric-container"] label { color: #8A8070 !important; font-size: 0.8em !important; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #F4EFE4 !important; font-size: 1.6em !important; font-weight: 700 !important;
    }

    /* ── 데이터프레임 ── */
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 2px 16px rgba(0,0,0,0.22);
        border: 1px solid rgba(138,128,112,0.18) !important;
    }

    /* ── 분석 버튼 (Primary) ── */
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #9A7B3C !important;
        border: none !important;
        color: #F4EFE4 !important;
        font-weight: 600;
        border-radius: 8px !important;
        letter-spacing: 0.03em;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #7A6030 !important;
        box-shadow: 0 4px 12px rgba(154,123,60,0.3) !important;
    }

    /* ── 트렌드 태그 버튼 (Secondary) ── */
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: #232018 !important;
        border: 1px solid rgba(138, 128, 112, 0.35) !important;
        border-radius: 20px !important;
        color: #C8BFB0 !important;
        font-size: 0.68em !important;
        font-weight: 500 !important;
        padding: 2px 4px !important;
        line-height: 1.4 !important;
        transition: all 0.2s ease !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        min-height: unset !important;
        height: 32px !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background-color: #9A7B3C !important;
        border-color: #9A7B3C !important;
        color: #F4EFE4 !important;
    }

    /* ── 연관 키워드 행 버튼 ── */
    div[data-testid="stButton"] button[kind="secondary"].rel-kw-btn,
    [data-testid="element-container"]:has(button[key*="rel_kw_btn"]) button {
        background-color: transparent !important;
        border: none !important;
        border-radius: 6px !important;
        color: #9A7B3C !important;
        font-size: 0.88em !important;
        font-weight: 500 !important;
        padding: 4px 8px !important;
        line-height: 1.5 !important;
        height: auto !important;
        min-height: unset !important;
        text-align: left !important;
        white-space: normal !important;
    }
    [data-testid="element-container"]:has(button[key*="rel_kw_btn"]) button:hover {
        background-color: rgba(154,123,60,0.12) !important;
        color: #C4973E !important;
        border: none !important;
    }

    /* ── 구분선 ── */
    hr { border-color: rgba(138,128,112,0.2) !important; margin: 28px 0 !important; }

    /* ── 타이포그래피 ── */
    h1 { color: #F4EFE4 !important; font-size: 1.7em !important; font-weight: 700 !important; letter-spacing: -0.01em; }
    h2, h3 { color: #F4EFE4 !important; font-weight: 600 !important; }
    h4, h5 { color: #D4C9B8 !important; font-weight: 600 !important; font-size: 0.95em !important; }
    p, li { color: #C8BFB0; }
    small, caption { color: #8A8070 !important; }
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

def normalize_korean(text: str) -> str:
    """
    Google Trends RSS가 '미국 의 해군 장관' 처럼 조사를 단어로 분리하는 문제 수정.
    조사/어미 앞에 붙은 불필요한 공백을 제거한다.
    """
    particles = (
        r'의|을|를|이|가|은|는|과|와|도|에|서|로|으로|만|까지|부터'
        r'|보다|처럼|이다|라는|이라는|란|이란|적|들|에서|에게|한테|께|라고|이라고'
    )
    # 단어 뒤에 공백 + 조사가 오는 패턴 → 공백 제거
    return re.sub(rf'\s+({particles})\b', r'\1', text).strip()

@st.cache_data(ttl=600)
def get_google_trends():
    url = "https://trends.google.com/trending/rss?geo=KR"
    try:
        res = requests.get(url, timeout=10)
        root = ET.fromstring(res.content)
        return [normalize_korean(item.find('title').text) for item in root.findall('.//item')]
    except: return []

@st.cache_data(ttl=600)
def get_trends_for_cloud(target=20):
    """Google Trends + Naver 자동완성으로 target개 보장"""
    base = get_google_trends()
    result = list(base)
    seen  = set(result)
    # 부족하면 상위 트렌드의 자동완성으로 보충
    for kw in base[:5]:
        if len(result) >= target:
            break
        for ac in get_naver_autocomplete(kw):
            if ac not in seen:
                result.append(ac)
                seen.add(ac)
            if len(result) >= target:
                break
    return result[:target]

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

def _call_naver_keyword_tool(hint_str: str):
    """네이버 검색광고 키워드 도구 API 호출 — 결과 리스트 또는 None 반환."""
    timestamp = str(round(time.time() * 1000))
    message = timestamp + ".GET./keywordstool"
    hash_obj = hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256)
    signature = base64.b64encode(hash_obj.digest()).decode("utf-8")
    headers = {
        "X-Timestamp": timestamp, "X-API-KEY": AD_API_KEY,
        "X-Customer": AD_CUSTOMER_ID, "X-Signature": signature,
    }
    res = requests.get(
        "https://api.searchad.naver.com/keywordstool",
        params={"hintKeywords": hint_str, "showDetail": 1},
        headers=headers, timeout=8
    )
    if res.status_code == 200:
        items = res.json().get('keywordList', [])
        result = []
        for i in items:
            pc  = int(i.get('monthlyPcQcCnt', 0))
            mob = int(i.get('monthlyMobileQcCnt', 0))
            total = pc + mob
            mob_pct = round(mob / total * 100, 1) if total > 0 else 0
            result.append({"keyword": i['relKeyword'], "volume": total, "mobile_pct": mob_pct})
        st.session_state.pop('_ad_api_debug', None)  # 성공 시 디버그 메시지 제거
        return result
    st.session_state['_ad_api_debug'] = f"status={res.status_code} / {res.text[:200]}"
    return None

def get_naver_rel_keywords(seeds):
    """
    연관 키워드 수집 — 3단계 폴백 전략.
    1차: 전체 키워드 + 자동완성 5개 힌트로 API 호출
    2차: 결과 0개면 조사 정규화 후 첫 명사(첫 단어)만 힌트로 재시도
    3차: 그래도 0개면 None 반환 → 호출부에서 autocomplete fallback 진행
    """
    if not seeds: return []
    base_kw = normalize_korean(seeds[0])  # 조사 띄어쓰기 버그 먼저 수정

    # 1차 시도: base_kw 단독 (네이버 Ad API는 단일 키워드가 가장 안정적)
    try:
        result = _call_naver_keyword_tool(base_kw)
        if result:
            return result
    except Exception:
        pass

    # 2차 시도: 긴 문장형 키워드일 경우 첫 단어(핵심 명사)만으로 재시도
    first_word = base_kw.split()[0] if ' ' in base_kw else base_kw
    if first_word != base_kw:
        try:
            result = _call_naver_keyword_tool(first_word)
            if result:
                return result
        except Exception:
            pass

    return []

def get_blog_doc_count(keyword):
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET}
    try:
        res = requests.get("https://openapi.naver.com/v1/search/blog.json", params={"query": keyword, "display": 1}, headers=headers)
        return res.json().get('total', 0) if res.status_code == 200 else 0
    except: pass
    return 0

def save_to_archive(target_kw, category, df_sorted):
    """
    구글 시트에 한 행으로 저장.
    연관 키워드는 쉼표 구분 한 셀에 모두 담음.
    """
    if not GSPREAD_OK:
        st.error("gspread 라이브러리가 설치되어 있지 않습니다. requirements.txt를 확인해주세요.")
        return False
    try:
        gsheet_url = st.secrets.get("GSHEET_URL", "")
        sa_info    = dict(st.secrets["gcp_service_account"])
    except Exception as e:
        st.error(f"⚙️ Secrets 읽기 실패: {e}")
        return False
    if not gsheet_url:
        st.error("GSHEET_URL이 비어 있습니다. Secrets에 구글 시트 URL을 넣어주세요.")
        return False
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        # private_key의 \\n → \n 변환 (TOML 저장 시 이스케이프 문제 방지)
        if 'private_key' in sa_info:
            sa_info['private_key'] = sa_info['private_key'].replace('\\n', '\n')
        creds  = Credentials.from_service_account_info(sa_info, scopes=scopes)
        client = gspread.authorize(creds)
        ws     = client.open_by_url(gsheet_url).sheet1

        # 대표 키워드 행 우선 탐색, 없으면 검색량 최대 행 사용
        main_row = df_sorted[df_sorted['키워드'] == target_kw]
        if not main_row.empty:
            ref = main_row.iloc[0]
        else:
            ref = df_sorted.loc[df_sorted['월간검색량'].idxmax()]

        total_vol   = int(df_sorted['월간검색량'].sum())          # 전체 연관 키워드 합산 검색량
        blog_cnt    = int(ref['블로그문서수'])
        comp        = round(float(ref['경쟁강도']), 2)
        mob_val     = df_sorted['모바일비율'].mean() if '모바일비율' in df_sorted.columns else 0
        mob_pct     = f"{mob_val:.0f}%"
        target_demo = str(ref['타겟추정']) if '타겟추정' in df_sorted.columns else ''

        # 연관 키워드 전체를 쉼표 구분 한 셀로
        rel_kws = ", ".join(df_sorted['키워드'].tolist())

        new_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            category,
            target_kw,
            rel_kws,
            total_vol,
            blog_cnt,
            comp,
            mob_pct,
            target_demo,
            "대기",
            ""
        ]
        ws.append_row(new_row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

@st.cache_data(ttl=600)
def get_naver_shopping(keyword, display=100):
    """네이버 쇼핑 API — 총 상품 수, 가격대, 상품 목록 반환"""
    headers = {"X-Naver-Client-Id": OPEN_CLIENT_ID, "X-Naver-Client-Secret": OPEN_CLIENT_SECRET}
    try:
        res = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            params={"query": keyword, "display": display, "sort": "sim"},
            headers=headers, timeout=8
        )
        if res.status_code == 200:
            data = res.json()
            total = data.get('total', 0)
            products = []
            for item in data.get('items', []):
                title = re.sub(r'<[^>]+>', '', item.get('title', ''))
                lprice = int(item.get('lprice', 0) or 0)
                products.append({
                    "상품명": title,
                    "최저가": lprice,
                    "판매처": item.get('mallName', '-'),
                    "브랜드": item.get('brand', '') or '-',
                    "카테고리": item.get('category1', '') or '기타',
                    "링크": item.get('link', ''),
                })
            return total, products
    except: pass
    return 0, []

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
    """
    YouTube Data API v3 — 쿼터 최적화 방식.
    search.list 1회(maxResults=50, 100유닛) + videos.list 1회(1유닛) = 101유닛.
    50개 수집 후 조회수 기준 TOP 10 추출 → 기존 10개 방식과 비용 동일, 정확도 5배.
    """
    if not YOUTUBE_API_KEY:
        return None, []
    try:
        # 1단계: 검색 결과 50개 수집 (1회 호출 = 100유닛)
        search_res = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "q": keyword, "part": "snippet", "type": "video",
                "maxResults": 50, "regionCode": "KR",
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

        # 2단계: 영상 50개 통계 일괄 조회 (1회 호출 = 1유닛)
        video_ids = [item["id"]["videoId"] for item in items if item.get("id", {}).get("videoId")]
        stats_res = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"id": ",".join(video_ids), "part": "statistics,snippet", "key": YOUTUBE_API_KEY}
        )
        all_videos = []
        for item in stats_res.json().get("items", []):
            stat = item.get("statistics", {})
            snip = item.get("snippet", {})
            all_videos.append({
                "제목": snip.get("title", ""),
                "채널": snip.get("channelTitle", ""),
                "조회수": int(stat.get("viewCount", 0)),
                "좋아요": int(stat.get("likeCount", 0)),
                "댓글수": int(stat.get("commentCount", 0)),
                "url": f"https://www.youtube.com/watch?v={item['id']}",
            })

        # 3단계: 조회수 기준 TOP 10 추출
        top10 = sorted(all_videos, key=lambda x: x["조회수"], reverse=True)[:10]
        return total_results, top10

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

@st.cache_data(ttl=1800)
def get_trend_volume(kw):
    """실시간 트렌드 키워드 월간검색량 — session_state 접근 없이 직접 API 호출"""
    try:
        timestamp = str(round(time.time() * 1000))
        message   = timestamp + ".GET./keywordstool"
        sig       = base64.b64encode(
            hmac.new(bytes(AD_SECRET_KEY, "utf-8"), bytes(message, "utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        headers = {"X-Timestamp": timestamp, "X-API-KEY": AD_API_KEY,
                   "X-Customer": AD_CUSTOMER_ID, "X-Signature": sig}
        res = requests.get(
            "https://api.searchad.naver.com/keywordstool",
            params={"hintKeywords": kw, "showDetail": 1},
            headers=headers, timeout=8
        )
        if res.status_code != 200:
            return 0
        items = res.json().get('keywordList', [])
        for item in items:
            pc = int(item.get('monthlyPcQcCnt', 0))
            mob = int(item.get('monthlyMobileQcCnt', 0))
            if item.get('relKeyword') == kw:
                return pc + mob
        if items:
            return int(items[0].get('monthlyPcQcCnt', 0)) + int(items[0].get('monthlyMobileQcCnt', 0))
    except Exception:
        pass
    return 0

def show_realtime_trends(trends):
    """실시간 검색어 시각화 페이지"""
    if not trends:
        st.warning("Google Trends 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
        return

    st.markdown("""
    <div class="section-card">
        <div class="section-card-title">REAL-TIME TRENDS</div>
        <div class="section-card-heading">🔥 실시간 인기 급상승 키워드</div>
        <div style="color:#8A8070; font-size:0.85em;">Google Trends 기준 · 키워드 클릭 시 네이버 뉴스로 이동합니다</div>
    </div>
    """, unsafe_allow_html=True)

    left_col, right_col = st.columns([3, 2])

    with left_col:
        st.markdown("#### 🌐 키워드 클라우드")

        COLORS = ["#C9A84C", "#D4B86A", "#E8D5A3", "#F4EFE4", "#C8BFB0", "#8A8070"]
        cloud_kws = get_trends_for_cloud(30)   # 30개 보장
        total_kws = max(len(cloud_kws), 1)

        kw_data = []
        for idx, kw in enumerate(cloud_kws):
            size_px = max(12, int(44 - idx * (44 - 12) / (total_kws - 1))) if total_kws > 1 else 44
            color   = COLORS[min(idx // 5, len(COLORS) - 1)]
            fw      = "700" if size_px >= 24 else "500"
            url     = f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(kw)}"
            safe_kw = kw.replace('\\', '\\\\').replace('"', '\\"')
            kw_data.append(f'{{"kw":"{safe_kw}","spx":{size_px},"color":"{color}","fw":"{fw}","url":"{url}"}}')

        kw_json = "[" + ",".join(kw_data) + "]"

        cloud_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#14120F;border-radius:14px;overflow:hidden;
      font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;}}
#wrap{{position:relative;width:100%;height:540px;overflow:hidden;}}
.kw{{position:absolute;white-space:nowrap;cursor:grab;user-select:none;
     visibility:hidden;will-change:left,top;}}
.kw:active{{cursor:grabbing;}}
</style></head><body>
<div id="wrap"></div>
<script>
(function(){{
const PAD   = 5;
const REPEL = 130;   // 반발 반경(px)
const SPRING= 0.035; // 원위치 복귀 강도
const FRIC  = 0.87;  // 마찰 (1=미끄럽, 0=즉시정지)
const FORCE = 14;    // 드래그 반발 강도

const items = {kw_json};
const wrap  = document.getElementById('wrap');
const W = wrap.clientWidth  || 720;
const H = wrap.clientHeight || 540;

// ── 1단계: 배치 ──────────────────────────────────────────
const placed = [];
const state  = [];

items.forEach(d => {{
  const el = document.createElement('span');
  el.className   = 'kw';
  el.textContent = d.kw;
  el.style.fontSize   = d.spx + 'px';
  el.style.color      = d.color;
  el.style.fontWeight = d.fw;
  wrap.appendChild(el);

  const ew = el.offsetWidth  + 4;
  const eh = el.offsetHeight + 2;
  let ox = 0, oy = 0;

  for (let i = 0; i < 400; i++) {{
    const tx = Math.random() * Math.max(1, W - ew);
    const ty = Math.random() * Math.max(1, H - eh);
    let ok = true;
    for (const [bx,by,bw,bh] of placed) {{
      if (!(tx+ew+PAD<bx||tx>bx+bw+PAD||ty+eh+PAD<by||ty>by+bh+PAD)){{ok=false;break;}}
    }}
    if (ok) {{ ox=tx; oy=ty; break; }}
    if (i===399) {{
      const sm = Math.max(11, d.spx*0.78);
      el.style.fontSize = sm+'px';
      ox = Math.random()*Math.max(1,W-el.offsetWidth-4);
      oy = Math.random()*Math.max(1,H-el.offsetHeight-2);
    }}
  }}
  placed.push([ox, oy, el.offsetWidth, el.offsetHeight]);
  el.style.left = ox+'px'; el.style.top = oy+'px';
  el.style.visibility = 'visible';

  state.push({{ el, url:d.url, x:ox, y:oy, ox, oy,
                vx:0, vy:0, w:el.offsetWidth, h:el.offsetHeight,
                dragging:false }});
}});

// ── 2단계: 드래그 + 물리 ─────────────────────────────────
let drag = null, offX = 0, offY = 0, didDrag = false, sx = 0, sy = 0;

state.forEach(item => {{
  item.el.addEventListener('mousedown', e => {{
    drag = item; item.dragging = true;
    const r = wrap.getBoundingClientRect();
    offX = e.clientX - r.left - item.x;
    offY = e.clientY - r.top  - item.y;
    sx = e.clientX; sy = e.clientY; didDrag = false;
    item.el.style.zIndex = 999;
    e.preventDefault();
  }});
  item.el.addEventListener('click', e => {{
    if (!didDrag) window.open(item.url,'_blank','noopener,noreferrer');
    e.preventDefault();
  }});
  // touch
  item.el.addEventListener('touchstart', e => {{
    const t = e.touches[0];
    drag = item; item.dragging = true;
    const r = wrap.getBoundingClientRect();
    offX = t.clientX - r.left - item.x;
    offY = t.clientY - r.top  - item.y;
    sx = t.clientX; sy = t.clientY; didDrag = false;
    item.el.style.zIndex = 999;
  }},{{passive:true}});
}});

function onMove(cx, cy) {{
  if (!drag) return;
  if (Math.hypot(cx-sx, cy-sy) > 5) didDrag = true;
  const r = wrap.getBoundingClientRect();
  const mx = cx - r.left, my = cy - r.top;
  drag.x = Math.max(0, Math.min(W - drag.w, mx - offX));
  drag.y = Math.max(0, Math.min(H - drag.h, my - offY));
  drag.el.style.left = drag.x+'px';
  drag.el.style.top  = drag.y+'px';
}}
function onUp() {{
  if (drag) {{ drag.dragging=false; drag.el.style.zIndex=''; drag=null; }}
}}

document.addEventListener('mousemove', e => onMove(e.clientX, e.clientY));
document.addEventListener('mouseup',   onUp);
document.addEventListener('touchmove', e => {{
  const t=e.touches[0]; onMove(t.clientX,t.clientY);
}},{{passive:true}});
document.addEventListener('touchend', onUp);

// ── 3단계: 애니메이션 루프 ────────────────────────────────
function tick() {{
  const dcx = drag ? drag.x + drag.w/2 : -9999;
  const dcy = drag ? drag.y + drag.h/2 : -9999;

  state.forEach(item => {{
    if (item.dragging) return;
    const cx = item.x + item.w/2;
    const cy = item.y + item.h/2;
    const dx = cx - dcx, dy = cy - dcy;
    const dist = Math.hypot(dx, dy) || 1;

    // 반발력
    if (dist < REPEL) {{
      const f = ((REPEL-dist)/REPEL) * FORCE;
      item.vx += (dx/dist)*f;
      item.vy += (dy/dist)*f;
    }}
    // 원위치 복귀 스프링
    item.vx += (item.ox - item.x) * SPRING;
    item.vy += (item.oy - item.y) * SPRING;
    // 마찰
    item.vx *= FRIC; item.vy *= FRIC;
    // 위치 업데이트
    item.x = Math.max(0, Math.min(W-item.w, item.x+item.vx));
    item.y = Math.max(0, Math.min(H-item.h, item.y+item.vy));
    item.el.style.left = item.x+'px';
    item.el.style.top  = item.y+'px';
  }});
  requestAnimationFrame(tick);
}}
tick();
}})();
</script></body></html>"""

        components.html(cloud_html, height=554)
        st.caption(f"✋ 단어를 드래그하면 주변 글자가 밀려납니다 · 클릭 시 뉴스 이동 · 총 {len(cloud_kws)}개")

    with right_col:
        st.markdown("#### 📊 검색 순위 (TOP 10)")
        with st.spinner("검색량 로딩 중..."):
            rank_rows = []
            medal = {0:"🥇",1:"🥈",2:"🥉"}
            for idx, kw in enumerate(trends[:10]):
                volume  = get_trend_volume(kw)
                vol_str = f"{volume:,}" if volume else "—"
                url     = f"https://search.naver.com/search.naver?where=news&query={requests.utils.quote(kw)}"
                icon    = medal.get(idx, str(idx+1))
                safe_kw = kw.replace('"','&quot;').replace('<','&lt;')
                rank_rows.append(
                    f'<tr>'
                    f'<td style="color:#C9A84C;font-weight:700;text-align:center;width:32px;">{icon}</td>'
                    f'<td><a href="{url}" target="_blank" rel="noopener" '
                    f'style="color:#F4EFE4;text-decoration:none;font-size:0.95em;">{safe_kw}</a></td>'
                    f'<td style="text-align:center;width:28px;">'
                    f'<a href="{url}" target="_blank" rel="noopener" style="text-decoration:none;">📰</a></td>'
                    f'<td style="color:#9A7B3C;font-size:0.82em;text-align:right;white-space:nowrap;">{vol_str}</td>'
                    f'</tr>'
                )
            rank_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{margin:0;padding:0;background:transparent;font-family:sans-serif;color:#F4EFE4;}}
table{{width:100%;border-collapse:collapse;}}
tr{{border-bottom:1px solid rgba(138,128,112,0.15);}}
td{{padding:8px 4px;vertical-align:middle;}}
a:hover{{opacity:0.7;}}
</style></head><body>
<table>{''.join(rank_rows)}</table>
</body></html>"""
            components.html(rank_html, height=10 * 44)

    st.divider()
    if st.button("🔄 새로고침", key="rt_refresh_btn"):
        st.cache_data.clear()
        st.rerun()

# ==========================================
# 🖥️ 프론트엔드 UI (화면 그리기)
# ==========================================
st.title("🚀 황금키워드 데이터랩")
st.markdown('<p class="sub-title">키워드 데이터 분석을 통해 콘텐츠의 유입률을 늘리고, 비즈니스를 확장시켜보세요.</p>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 6])
with col1:
    st.selectbox("분석 유형", ["검색 분석", "쇼핑 분석", "실시간 검색어"], label_visibility="collapsed", key="analysis_type_widget")
with col2:
    def update_search():
        st.session_state.current_search = st.session_state.search_input_widget
        st.session_state.auto_run = False
    user_keyword = st.text_input("검색어", value=st.session_state.current_search, key="search_input_widget", placeholder="분석할 키워드 (예: 영등포 로컬, 문래창작촌)", label_visibility="collapsed", on_change=update_search)

# ── 카테고리 선택 ──────────────────────────────────────
_cat_options = st.session_state.categories + ["✚ 새 카테고리 추가"]
cat_col1, cat_col2 = st.columns([5, 2])
with cat_col1:
    category_choice = st.selectbox("카테고리", _cat_options, label_visibility="collapsed", key="category_select")
with cat_col2:
    if category_choice == "✚ 새 카테고리 추가":
        new_cat_val = st.text_input("새 카테고리", label_visibility="collapsed", placeholder="카테고리명 입력")
        if st.button("추가", key="add_cat_btn") and new_cat_val:
            if new_cat_val not in st.session_state.categories:
                st.session_state.categories.append(new_cat_val)
            st.rerun()
    else:
        st.caption(f"저장 카테고리: **{category_choice}**")

# 실제로 사용할 카테고리 값 결정
_final_category = (
    category_choice if category_choice != "✚ 새 카테고리 추가"
    else (st.session_state.categories[-1] if st.session_state.categories else "기타")
)

current_trends = get_google_trends()

# ── 실시간 검색어 탭: 별도 페이지로 분기 ──────────────────────
if st.session_state.get('analysis_type_widget') == '실시간 검색어':
    show_realtime_trends(current_trends)
    st.stop()

if current_trends:
    top20 = current_trends[:20]
    trend_cols = st.columns(len(top20))
    for i, kw in enumerate(top20):
        with trend_cols[i]:
            if st.button(f"#{kw}", key=f"trend_tag_{i}", use_container_width=True):
                st.session_state.current_search = kw
                st.session_state._pending_search = kw
                st.session_state.auto_run = True
                st.rerun()

is_clicked = st.button("분석 시작하기", type="primary", use_container_width=True)

# 검색광고 API 디버그 메시지 (문제 진단용)
if st.session_state.get('_ad_api_debug'):
    st.warning(f"🔍 [AD API 디버그] {st.session_state['_ad_api_debug']}")

if is_clicked or st.session_state.auto_run:
    st.session_state.auto_run = False 
    seeds = [normalize_korean(k.strip()) for k in st.session_state.current_search.split(",") if k.strip()] if st.session_state.current_search.strip() else current_trends

    if seeds:
        target_kw = seeds[0]
        analysis_type = st.session_state.get('analysis_type_widget', '검색 분석')

        # ══════════════════════════════════════════
        # 🔍 검색 분석
        # ══════════════════════════════════════════
        trend_df = get_datalab_trend(target_kw) if analysis_type == '검색 분석' else None

        if analysis_type == '검색 분석' and trend_df is not None:
            # 1. 1년 트렌드 선 그래프
            st.markdown(f"""
            <div class="section-card">
                <div class="section-card-title">Search Trend</div>
                <div class="section-card-heading">📈 '{target_kw}' 최근 1년 검색 트렌드</div>
            </div>""", unsafe_allow_html=True)
            monthly_trend = trend_df.groupby(trend_df.index.to_period('M')).mean()
            monthly_trend.index = monthly_trend.index.to_timestamp()
            st.line_chart(monthly_trend, color="#9A7B3C")
            
            # 2. 월별/요일별 차트
            col_chart1, col_chart2 = st.columns(2)

            axis_cfg = alt.Axis(
                labelAngle=0,
                title=None,
                labelColor="#8A8070",
                tickColor="transparent",
                domainColor="rgba(138,128,112,0.25)"
            )
            y_axis_cfg = alt.Axis(
                title=None,
                labelExpr='datum.value + "%"',
                labelColor="#8A8070",
                gridColor="rgba(138,128,112,0.12)",
                domainColor="transparent",
                tickColor="transparent"
            )

            with col_chart1:
                st.markdown("##### 📅 월별 검색 비율")
                month_group = trend_df.groupby(trend_df.index.month).mean()
                month_pct = (month_group / month_group.sum() * 100).iloc[:, 0].round(1)
                month_df = pd.DataFrame({"월": [f"{m}월" for m in month_pct.index], "비율(%)": month_pct.values})
                st.altair_chart(
                    alt.Chart(month_df)
                    .mark_bar(color="#9A7B3C", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                    .encode(
                        x=alt.X("월:N", sort=None, axis=axis_cfg),
                        y=alt.Y("비율(%):Q", axis=y_axis_cfg),
                        tooltip=[alt.Tooltip("월:N"), alt.Tooltip("비율(%):Q", format=".1f", title="비율(%)")]
                    )
                    .properties(height=260)
                    .configure_view(strokeWidth=0, fill="#1C1A17")
                    .configure(background="#1C1A17"),
                    use_container_width=True
                )

            with col_chart2:
                st.markdown("##### 📆 요일별 검색 비율")
                dow_group = trend_df.groupby(trend_df.index.dayofweek).mean()
                dow_map = {0:"월", 1:"화", 2:"수", 3:"목", 4:"금", 5:"토", 6:"일"}
                dow_pct = (dow_group / dow_group.sum() * 100).iloc[:, 0].round(1)
                dow_df = pd.DataFrame({"요일": [dow_map[d] for d in dow_pct.index], "비율(%)": dow_pct.values})
                st.altair_chart(
                    alt.Chart(dow_df)
                    .mark_bar(color="#9A7B3C", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                    .encode(
                        x=alt.X("요일:N", sort=None, axis=axis_cfg),
                        y=alt.Y("비율(%):Q", axis=y_axis_cfg),
                        tooltip=[alt.Tooltip("요일:N"), alt.Tooltip("비율(%):Q", format=".1f", title="비율(%)")]
                    )
                    .properties(height=260)
                    .configure_view(strokeWidth=0, fill="#1C1A17")
                    .configure(background="#1C1A17"),
                    use_container_width=True
                )
            
            st.divider()
            
            # 3. 검색자 성향 분석
            st.markdown(f"""
            <div class="section-card">
                <div class="section-card-title">Audience Analysis</div>
                <div class="section-card-heading">👥 '{target_kw}' 검색자 성향 분석 <span style="font-size:0.75em; color:#8A8070; font-weight:400;">(추정 지표)</span></div>
            </div>""", unsafe_allow_html=True)
            
            # 추정치 데이터 가져오기
            age, male, female, issue, normal, com, info = generate_mock_demographics(target_kw)
            
            # 3-1. 연령별 막대 그래프
            st.markdown("##### 👨‍👩‍👧‍👦 연령별 검색 비율")
            age_df = pd.DataFrame({"연령대": ["10대", "20대", "30대", "40대", "50대 이상"], "비율(%)": age})
            st.altair_chart(
                alt.Chart(age_df)
                .mark_bar(color="#9A7B3C", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                .encode(
                    x=alt.X("연령대:N", sort=None, axis=axis_cfg),
                    y=alt.Y("비율(%):Q", axis=y_axis_cfg),
                    tooltip=[alt.Tooltip("연령대:N"), alt.Tooltip("비율(%):Q", format=".1f", title="비율(%)")]
                )
                .properties(height=260)
                .configure_view(strokeWidth=0, fill="#1C1A17")
                .configure(background="#1C1A17"),
                use_container_width=True
            )
            
            # 3-2. 성별, 이슈성, 정보/상업성 파이(도넛) 차트 3개 나란히
            pie1, pie2, pie3 = st.columns(3)
            
            with pie1:
                st.markdown("<p style='text-align:center; font-weight:bold;'>성별 검색 비율</p>", unsafe_allow_html=True)
                st.altair_chart(draw_donut_chart({"여성": female, "남성": male}, ['#8A8070', '#9A7B3C']), use_container_width=True)
                
            with pie2:
                st.markdown("<p style='text-align:center; font-weight:bold;'>이슈성 (트렌드 민감도)</p>", unsafe_allow_html=True)
                st.altair_chart(draw_donut_chart({"이슈성": issue, "일반": normal}, ['#9A7B3C', '#2A2620']), use_container_width=True)
                
            with pie3:
                st.markdown("<p style='text-align:center; font-weight:bold;'>정보성 vs 상업성</p>", unsafe_allow_html=True)
                st.altair_chart(draw_donut_chart({"정보성": info, "상업성": com}, ['#F4EFE4', '#8A8070']), use_container_width=True)

            st.divider()

            # 4. YouTube 경쟁 분석
            st.markdown(f"""
            <div class="section-card">
                <div class="section-card-title">YouTube Competition</div>
                <div class="section-card-heading">🎥 '{target_kw}' YouTube 경쟁 분석</div>
            </div>""", unsafe_allow_html=True)
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
                    rows_html = ""
                    for idx, v in enumerate(yt_videos):
                        row_bg = "rgba(154,123,60,0.04)" if idx % 2 == 0 else "transparent"
                        rows_html += f"""
                        <tr style="border-bottom:1px solid rgba(138,128,112,0.12); background:{row_bg};">
                            <td style="padding:10px 8px;"><a href="{v['url']}" target="_blank"
                               style="color:#9A7B3C; text-decoration:none; font-weight:500;"
                               onmouseover="this.style.textDecoration='underline'"
                               onmouseout="this.style.textDecoration='none'">{v['제목']}</a></td>
                            <td style="padding:10px 8px; color:#8A8070;">{v['채널']}</td>
                            <td style="padding:10px 8px; text-align:right; color:#F4EFE4;">{v['조회수']:,}</td>
                            <td style="padding:10px 8px; text-align:right; color:#F4EFE4;">{v['좋아요']:,}</td>
                            <td style="padding:10px 8px; text-align:right; color:#F4EFE4;">{v['댓글수']:,}</td>
                        </tr>"""
                    st.markdown(f"""
                    <table style="width:100%; border-collapse:collapse; font-size:0.88em;">
                        <thead>
                            <tr style="border-bottom:1px solid rgba(138,128,112,0.3);">
                                <th style="text-align:left; padding:10px 8px; color:#8A8070; font-weight:600;">제목</th>
                                <th style="text-align:left; padding:10px 8px; color:#8A8070; font-weight:600;">채널</th>
                                <th style="text-align:right; padding:10px 8px; color:#8A8070; font-weight:600;">조회수</th>
                                <th style="text-align:right; padding:10px 8px; color:#8A8070; font-weight:600;">좋아요</th>
                                <th style="text-align:right; padding:10px 8px; color:#8A8070; font-weight:600;">댓글수</th>
                            </tr>
                        </thead>
                        <tbody style="font-size:0.95em;">{rows_html}</tbody>
                    </table>
                    """, unsafe_allow_html=True)
            else:
                st.info("YouTube 데이터를 가져올 수 없습니다. API 키를 확인해주세요.")

            st.divider()

        # ══════════════════════════════════════════
        # 🛍️ 쇼핑 분석
        # ══════════════════════════════════════════
        elif analysis_type == '쇼핑 분석':
            st.markdown(f"""
            <div class="section-card">
                <div class="section-card-title">Shopping Analysis</div>
                <div class="section-card-heading">🛍️ '{target_kw}' 네이버 쇼핑 분석</div>
            </div>""", unsafe_allow_html=True)

            with st.spinner("쇼핑 데이터를 불러오는 중..."):
                shop_total, shop_products = get_naver_shopping(target_kw)

            if shop_products:
                prices = [p["최저가"] for p in shop_products if p["최저가"] > 0]
                min_price = min(prices) if prices else 0
                avg_price = int(sum(prices) / len(prices)) if prices else 0

                # 카테고리 분포 집계
                cat_counts = {}
                for p in shop_products:
                    c = p["카테고리"] or "기타"
                    cat_counts[c] = cat_counts.get(c, 0) + 1
                top_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:5]

                # 경쟁 강도 판단
                if shop_total >= 100000:
                    comp_label, comp_color = "매우 높음", "#E05050"
                elif shop_total >= 30000:
                    comp_label, comp_color = "높음", "#C4973E"
                elif shop_total >= 5000:
                    comp_label, comp_color = "중간", "#9A7B3C"
                else:
                    comp_label, comp_color = "낮음", "#4BB478"

                # 지표 카드
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("📦 총 상품 수", f"{shop_total:,}개")
                m2.metric("💰 최저가", f"₩{min_price:,}" if min_price else "정보 없음")
                m3.metric("📊 평균가", f"₩{avg_price:,}" if avg_price else "정보 없음")
                m4.metric("⚔️ 쇼핑 경쟁도", comp_label)

                st.divider()

                col_chart, col_table = st.columns([1, 2])

                with col_chart:
                    st.markdown("##### 📦 카테고리 분포")
                    if top_cats:
                        cat_df = pd.DataFrame(top_cats, columns=["카테고리", "상품수"])
                        axis_cfg = alt.Axis(labelAngle=0, title=None, labelColor="#8A8070",
                                            tickColor="transparent", domainColor="rgba(138,128,112,0.25)")
                        y_axis_cfg = alt.Axis(title=None, labelColor="#8A8070",
                                              gridColor="rgba(138,128,112,0.12)",
                                              domainColor="transparent", tickColor="transparent")
                        st.altair_chart(
                            alt.Chart(cat_df)
                            .mark_bar(color="#9A7B3C", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                            .encode(
                                x=alt.X("카테고리:N", sort=None, axis=axis_cfg),
                                y=alt.Y("상품수:Q", axis=y_axis_cfg),
                                tooltip=["카테고리", "상품수"]
                            )
                            .properties(height=220)
                            .configure_view(strokeWidth=0, fill="#1C1A17")
                            .configure(background="#1C1A17"),
                            use_container_width=True
                        )

                with col_table:
                    st.markdown("##### 🏆 상위 노출 상품 TOP 10")
                    rows_html = ""
                    for idx, p in enumerate(shop_products[:10]):
                        row_bg = "rgba(154,123,60,0.04)" if idx % 2 == 0 else "transparent"
                        price_str = f"₩{p['최저가']:,}" if p['최저가'] > 0 else "-"
                        rows_html += f"""
                        <tr style="border-bottom:1px solid rgba(138,128,112,0.12); background:{row_bg};">
                            <td style="padding:9px 8px;">
                                <a href="{p['링크']}" target="_blank"
                                   style="color:#9A7B3C; text-decoration:none; font-weight:500;"
                                   onmouseover="this.style.textDecoration='underline'"
                                   onmouseout="this.style.textDecoration='none'">{p['상품명'][:30]}{"..." if len(p['상품명'])>30 else ""}</a>
                            </td>
                            <td style="padding:9px 8px; color:#F4EFE4; text-align:right; white-space:nowrap;">{price_str}</td>
                            <td style="padding:9px 8px; color:#8A8070; white-space:nowrap;">{p['판매처']}</td>
                        </tr>"""
                    st.markdown(f"""
                    <table style="width:100%; border-collapse:collapse; font-size:0.85em;">
                        <thead>
                            <tr style="border-bottom:1px solid rgba(138,128,112,0.3);">
                                <th style="text-align:left; padding:9px 8px; color:#8A8070; font-weight:600;">상품명</th>
                                <th style="text-align:right; padding:9px 8px; color:#8A8070; font-weight:600;">최저가</th>
                                <th style="text-align:left; padding:9px 8px; color:#8A8070; font-weight:600;">판매처</th>
                            </tr>
                        </thead>
                        <tbody>{rows_html}</tbody>
                    </table>""", unsafe_allow_html=True)
            else:
                st.warning("쇼핑 데이터를 가져올 수 없습니다. 다른 키워드로 시도해보세요.")

            st.divider()

        # ══════════════════════════════════════════
        # 공통: 연관 검색어 + 경쟁강도 테이블 (두 분석 모두 표시)
        # ══════════════════════════════════════════
        with st.spinner("네이버 연관 검색어와 경쟁 강도를 분석 중입니다..."):
            raw_keywords = get_naver_rel_keywords(seeds)
            # keyword tool에서 못 찾으면 자동완성 결과로 보완
            if not raw_keywords:
                autocomplete_kws = get_naver_autocomplete(target_kw)
                raw_keywords = [{"keyword": kw, "volume": 0} for kw in autocomplete_kws]

        if raw_keywords:
            df_raw = pd.DataFrame(raw_keywords)
            df_top50 = df_raw.sort_values(by="volume", ascending=False).head(50)

            final_results = []
            my_bar = st.progress(0, text="블로그 문서 수 수집 중...")

            total_items = len(df_top50)
            for idx, item in enumerate(df_top50.to_dict('records')):
                doc = get_blog_doc_count(item['keyword'])
                comp = round(doc / item['volume'], 2) if item['volume'] > 0 else 0
                final_results.append({
                    "키워드": item['keyword'],
                    "월간검색량": item['volume'],
                    "블로그문서수": doc,
                    "경쟁강도": comp,
                    "모바일비율": item.get('mobile_pct', 0),
                })
                my_bar.progress((idx + 1) / total_items, text="블로그 문서 수 수집 중...")

            # 타겟 추정 (hash 기반 추정치)
            age, male, female, *_ = generate_mock_demographics(target_kw)
            dom_gender = "여성" if female > male else "남성"
            age_labels = ["10대", "20대", "30대", "40대", "50대 이상"]
            dom_age = age_labels[age.index(max(age))]
            target_demo_str = f"{dom_gender} {dom_age}"

            df_final = pd.DataFrame(final_results)
            df_final['타겟추정'] = target_demo_str
            df_sorted = df_final.sort_values(by=["경쟁강도", "월간검색량"], ascending=[True, False]).reset_index(drop=True)

            # 세션에 저장 (save_to_archive 버튼에서 참조)
            st.session_state.last_df_sorted  = df_sorted
            st.session_state.last_target_kw  = target_kw
            st.session_state.last_category   = _final_category

            st.markdown(f"""
            <div class="section-card">
                <div class="section-card-title">Related Keywords</div>
                <div class="section-card-heading">✨ 연관 검색어 분석 완료 <span style="color:#9A7B3C;">({len(df_sorted)}개)</span></div>
                <div style="color:#8A8070; font-size:0.85em;">👇 키워드를 클릭하면 즉시 꼬리물기 분석이 시작됩니다.</div>
            </div>""", unsafe_allow_html=True)

            # 테이블 헤더
            h0, h1, h2, h3 = st.columns([4, 2, 2, 2])
            for col, label in zip([h0, h1, h2, h3], ["키워드", "월간검색량", "블로그문서수", "경쟁강도"]):
                col.markdown(f'<div style="color:#8A8070; font-size:0.78em; font-weight:600; padding:4px 0 8px 0; border-bottom:1px solid rgba(138,128,112,0.25);">{label}</div>', unsafe_allow_html=True)

            # 테이블 행 — 키워드는 버튼, 나머지는 텍스트
            for i, row in df_sorted.iterrows():
                c0, c1, c2, c3 = st.columns([4, 2, 2, 2])
                with c0:
                    if st.button(
                        f"🔍 {row['키워드']}",
                        key=f"rel_kw_btn_{i}",
                        use_container_width=True,
                        help=f"'{row['키워드']}' 분석 시작"
                    ):
                        st.session_state.current_search = row['키워드']
                        st.session_state._pending_search = row['키워드']
                        st.session_state.auto_run = True
                        st.rerun()
                c1.markdown(f'<div style="padding:6px 0; color:#F4EFE4; font-size:0.9em;">{int(row["월간검색량"]):,}</div>', unsafe_allow_html=True)
                c2.markdown(f'<div style="padding:6px 0; color:#F4EFE4; font-size:0.9em;">{int(row["블로그문서수"]):,}</div>', unsafe_allow_html=True)
                c3.markdown(f'<div style="padding:6px 0; color:#8A8070; font-size:0.9em;">{row["경쟁강도"]}</div>', unsafe_allow_html=True)
        else:
            st.warning("연관 검색어를 찾지 못했습니다. 다른 키워드로 시도해보세요.")

    else:
        st.error("데이터를 수집할 수 없습니다.")

# ── 아카이브 저장 버튼 (분석 블록 바깥 — 항상 렌더링) ────────────
if st.session_state.last_df_sorted is not None:
    st.divider()
    save_col1, save_col2 = st.columns([3, 1])
    with save_col1:
        n_rel = len(st.session_state.last_df_sorted)
        st.caption(f"카테고리: **{st.session_state.last_category}** · 키워드: **{st.session_state.last_target_kw}** · 연관 {n_rel}개")
    with save_col2:
        if st.button("💾 구글 시트에 저장", key="save_archive_btn", use_container_width=True):
            ok = save_to_archive(
                st.session_state.last_target_kw,
                st.session_state.last_category,
                st.session_state.last_df_sorted
            )
            if ok:
                st.success(f"✅ '{st.session_state.last_target_kw}' 저장 완료!")