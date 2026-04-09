name: Daily Golden Keyword Scraper

on:
  schedule:
    - cron: '0 23 * * *'
  workflow_dispatch: 

permissions:
  contents: write

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: 저장소 데이터 가져오기
        uses: actions/checkout@v4

      - name: 파이썬 설치
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: 필요한 도구 설치
        run: pip install requests pandas

      - name: 분석 스크립트 실행
        env:
          AD_API_KEY: ${{ secrets.AD_API_KEY }}
          AD_SECRET_KEY: ${{ secrets.AD_SECRET_KEY }}
          AD_CUSTOMER_ID: ${{ secrets.AD_CUSTOMER_ID }}
          OPEN_CLIENT_ID: ${{ secrets.OPEN_CLIENT_ID }}
          OPEN_CLIENT_SECRET: ${{ secrets.OPEN_CLIENT_SECRET }}
        run: python main.py

      - name: 결과 파일 자동 저장 및 업로드
        uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: "📈 황금키워드 리스트 업데이트"
          file_pattern: 'daily_golden_keywords.csv'
