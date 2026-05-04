from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tradingagents.api.app import app


def build_mock_ohlc(count: int = 80) -> list[dict]:
    candles: list[dict] = []
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    close = 1.0850
    for index in range(count):
        open_price = close
        close = open_price + 0.00008 + (0.00003 if index % 5 == 0 else -0.00001)
        candles.append(
            {
                "timestamp": (timestamp + timedelta(hours=index)).isoformat(),
                "open": round(open_price, 5),
                "high": round(max(open_price, close) + 0.00035, 5),
                "low": round(min(open_price, close) - 0.00030, 5),
                "close": round(close, 5),
                "volume": 1000 + index,
            }
        )
    return candles


def main() -> None:
    client = TestClient(app)
    response = client.post(
        "/analyze",
        json={
            "symbol": "EURUSD",
            "ohlc": build_mock_ohlc(),
            "account_equity": 10_000,
            "risk_per_trade": 0.01,
            "min_rr": 2.0,
        },
    )
    response.raise_for_status()
    print(response.json())


if __name__ == "__main__":
    main()
