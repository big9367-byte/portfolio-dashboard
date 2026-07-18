#!/usr/bin/env python3
"""index.html의 DEFAULT_DATA 보유종목 평가금액을 최신 시세로 갱신한다.

야후 파이낸스 시세를 사용한다. 미국 종목은 USD/KRW 환율을 곱해 원화로
환산하고, KRX 종목은 야후의 .KS 접미사 심볼로 조회한다. 조회에 실패한
종목은 기존 값을 유지한다.
"""

import datetime
import json
import re
import sys
import urllib.parse
import urllib.request
import zoneinfo

INDEX_PATH = "index.html"
KST = zoneinfo.ZoneInfo("Asia/Seoul")

HOLDING_RE = re.compile(
    r'\{ id: "(?P<id>[^"]+)", account: "[^"]+", name: "(?P<name>[^"]+)", '
    r'sector: "[^"]+", cost: \d+, value: (?P<value>\d+), '
    r'symbol: "(?P<symbol>[^"]*)", exchange: "(?P<exchange>[^"]*)", '
    r'currency: "(?P<currency>[^"]*)", quantity: (?P<quantity>[\d.]+)'
)


def fetch_price(symbol):
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval=1d&range=1d"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    result = data["chart"]["result"][0]["meta"]
    price = result.get("regularMarketPrice")
    if not isinstance(price, (int, float)) or price <= 0:
        raise ValueError(f"{symbol}: no price in response")
    return float(price)


def yahoo_symbol(symbol, exchange):
    return f"{symbol}.KS" if exchange == "XKRX" else symbol


def main():
    with open(INDEX_PATH, encoding="utf-8") as f:
        html = f.read()

    try:
        fx = fetch_price("KRW=X")
    except Exception as e:
        print(f"환율 조회 실패, 중단: {e}", file=sys.stderr)
        return 1

    updated, skipped = [], []

    def replace(match):
        d = match.groupdict()
        if d["exchange"] not in ("US", "XKRX") or not d["symbol"]:
            return match.group(0)
        try:
            price = fetch_price(yahoo_symbol(d["symbol"], d["exchange"]))
        except Exception as e:
            skipped.append(f"{d['name']}({d['symbol']}): {e}")
            return match.group(0)
        rate = fx if d["currency"] == "USD" else 1.0
        new_value = round(float(d["quantity"]) * price * rate)
        updated.append(f"{d['name']}: {d['value']} -> {new_value}")
        return match.group(0).replace(
            f"value: {d['value']},", f"value: {new_value},", 1
        )

    html = HOLDING_RE.sub(replace, html)

    today = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    html = re.sub(r'asOfDate: "\d{4}-\d{2}-\d{2}"', f'asOfDate: "{today}"', html)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"USD/KRW {fx:.2f}, 기준일 {today}")
    for line in updated:
        print("갱신:", line)
    for line in skipped:
        print("건너뜀:", line, file=sys.stderr)
    if not updated:
        print("갱신된 종목이 없습니다.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
