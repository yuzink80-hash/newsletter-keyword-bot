name: Daily Golden Keyword Scraper

on:
  schedule:
    - cron: '0 23 * * *'
  workflow_dispatch: 

# [추가] 로봇에게 쓰기 권한을 한 번 더 명시적으로 허용합니다.
permissions:
  contents: write

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install requests pandas

      - name: Run Python script
        env:
          AD_API_KEY: ${{ secrets.AD_API_KEY }}
          AD_SECRET_KEY: ${{ secrets.AD_SECRET_KEY }}
          AD_CUSTOMER_ID: ${{ secrets.AD_CUSTOMER_ID }}
          OPEN_CLIENT_ID: ${{ secrets.OPEN_CLIENT_ID }}
          OPEN_CLIENT_SECRET: ${{ secrets.OPEN_CLIENT_SECRET }}
        run: python main.py

      - name: Commit and Push results
        # [수정] 인증 토큰을 직접 사용하여 128 에러를 강제로 돌파합니다.
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          
          # 파일이 실제로 생성되었는지 확인 후 진행
          if [ -f daily_golden_keywords.csv ]; then
            git add daily_golden_keywords.csv
            git commit -m "📈 황금키워드 자동 업데이트" || echo "변경 사항 없음"
            git push "https://${{ github.actor }}:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git" main
          else
            echo "🚨 CSV 파일이 생성되지 않아 Push를 중단합니다."
          fi
