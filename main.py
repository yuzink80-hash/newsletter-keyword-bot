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
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install requests pandas

      - name: Run script
        env:
          AD_API_KEY: ${{ secrets.AD_API_KEY }}
          AD_SECRET_KEY: ${{ secrets.AD_SECRET_KEY }}
          AD_CUSTOMER_ID: ${{ secrets.AD_CUSTOMER_ID }}
          OPEN_CLIENT_ID: ${{ secrets.OPEN_CLIENT_ID }}
          OPEN_CLIENT_SECRET: ${{ secrets.OPEN_CLIENT_SECRET }}
        run: python main.py

      - name: Commit and Push
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          
          # 파일이 생겼을 때만 강제로 밀어넣기
          if [ -f daily_golden_keywords.csv ]; then
            git add daily_golden_keywords.csv
            git commit -m "📈 자동 업데이트" || echo "변경 사항 없음"
            # 내 아이디로 직접 푸시하는 가장 강력한 방법
            git push "https://${{ github.actor }}:${{ secrets.GITHUB_TOKEN }}@github.com/${{ github.repository }}.git" main
          else
            echo "🚨 CSV 파일이 없습니다. 파이썬 실행 결과를 확인하세요."
          fi
