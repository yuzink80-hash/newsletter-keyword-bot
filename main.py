# 웹 화면 구성을 위한 Streamlit 실행부
if __name__ == "__main__":
    st.set_page_config(page_title="황금키워드 분석기", page_icon="📈", layout="wide")
    st.title("🚀 황금키워드 자동 분석기")
    st.write("원하는 키워드를 직접 검색하거나, 구글 실시간 트렌드를 기반으로 최적의 네이버 연관 검색어를 찾습니다.")
    
    # 🌟 새롭게 추가된 검색어 입력 칸!
    user_keyword = st.text_input(
        "🔍 분석하고 싶은 핵심 키워드를 입력하세요", 
        placeholder="예: 영등포 로컬, 러닝화, 미국주식 (비워두면 구글 실시간 트렌드로 자동 분석합니다)"
    )
    
    if st.button("분석 시작하기", type="primary"):
        seeds = []
        
        # 1. 사용자가 직접 키워드를 입력한 경우
        if user_keyword.strip():
            seeds = [user_keyword.strip()]
            st.success(f"🎯 '{user_keyword}' 키워드를 바탕으로 네이버 연관 검색어를 확장합니다.")
        
        # 2. 아무것도 입력하지 않은 경우 (기존 방식: 구글 트렌드)
        else:
            with st.spinner("구글 트렌드 실시간 키워드를 수집하고 있습니다..."):
                seeds = get_google_trends()
            if seeds:
                st.success(f"📈 구글 트렌드에서 {len(seeds)}개의 키워드를 찾았습니다.")
        
        # 3. 공통 분석 로직 (네이버 연관 검색어 확장)
        if seeds:
            with st.spinner("네이버 연관 검색어와 검색량을 분석 중입니다..."):
                raw_keywords = get_naver_rel_keywords(seeds)
            
            if raw_keywords:
                df_raw = pd.DataFrame(raw_keywords)
                # 검색량 상위 50개만 추출
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
                
                # 결과 저장 및 화면 출력
                df_sorted.to_csv("daily_golden_keywords.csv", index=False, encoding="utf-8-sig")
                st.subheader(f"✨ 분석 완료! (총 {len(df_sorted)}개)")
                st.dataframe(df_sorted, use_container_width=True)
            else:
                st.warning("분석할 데이터를 찾지 못했습니다.")
        else:
            st.error("분석을 시작할 기초 키워드를 찾지 못했습니다.")