import time, requests, hashlib, hmac, base64

# 🚨 아래 3곳에 실제 값을 붙여넣어 주세요!
API_KEY = "0100000000da393051bc0ad52c63ef41b601b7fcce544c88645d22f4c40cd79d77e8e0d097"
SECRET_KEY = "AQAAAADHv6i7xheOLlXkWUe0dEuS+BOXWrp8ukJA7MPaYdqUXw=="
CUSTOMER_ID = "4348120"

print("📡 네이버 다이렉트 통신 테스트를 시작합니다...")
ts = str(round(time.time() * 1000))
msg = f"{ts}.GET./keywordstool"
sign = base64.b64encode(hmac.new(bytes(SECRET_KEY, "utf-8"), bytes(msg, "utf-8"), hashlib.sha256).digest()).decode("utf-8")

headers = {
    "X-Timestamp": ts, 
    "X-API-KEY": API_KEY, 
    "X-Customer": CUSTOMER_ID, 
    "X-Signature": sign
}

# 방송, 편집 키워드로 데이터가 잘 오는지 찔러봅니다.
r = requests.get("https://api.searchad.naver.com/keywordstool", params={"hintKeywords": "방송,편집", "showDetail": 1}, headers=headers)

print(f"👉 최종 응답 코드: {r.status_code}")
if r.status_code == 200:
    print("✅ 성공! 네이버가 정상적으로 데이터를 보내줍니다.")
else:
    print(f"❌ 실패! 네이버의 거절 사유: {r.text}")
