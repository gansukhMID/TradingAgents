from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi.testclient import TestClient

from tradingagents.api.app import app


def build_mock_ohlc(count: int = 200, run_index: int = 0) -> list[dict[str, Any]]:
    candles: list[dict[str, Any]] = []
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    close = 1.0850 + run_index * 0.0002
    for index in range(count):
        open_price = close
        close = open_price + 0.00008 + (0.00003 if index % 5 == 0 else -0.00001)
        candles.append(
            {
                "timestamp": (timestamp + timedelta(minutes=15 * index)).isoformat(),
                "open": round(open_price, 5),
                "high": round(max(open_price, close) + 0.00035, 5),
                "low": round(min(open_price, close) - 0.00030, 5),
                "close": round(close, 5),
                "volume": 1000 + index,
            }
        )
    return candles


def _payload(run_index: int, use_mock_ohlc: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "symbol": "EURUSD",
        "timeframe": "15m",
        "lookback": 200,
        "account_equity": 10_000,
        "risk_per_trade": 0.01,
        "min_rr": 2.0,
    }
    if use_mock_ohlc:
        payload["ohlc"] = build_mock_ohlc(run_index=run_index)
    return payload


def call_local(payload: dict[str, Any]) -> dict[str, Any]:
    client = TestClient(app)
    response = client.post("/analyze", json=payload)
    response.raise_for_status()
    return response.json()


def call_server(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(f"{base_url.rstrip('/')}/analyze", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Call /analyze repeatedly and print JSON output.")
    parser.add_argument("--base-url", default="local", help="Use 'local' for TestClient or a server URL.")
    parser.add_argument("--runs", type=int, default=3, help="Number of /analyze calls to execute.")
    parser.add_argument(
        "--use-mt5",
        action="store_true",
        help="Omit mock OHLC so the backend attempts MetaTrader 5 and falls back if needed.",
    )
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    use_mock_ohlc = not args.use_mt5

    for run_index in range(args.runs):
        payload = _payload(run_index, use_mock_ohlc)
        result = (
            call_local(payload)
            if args.base_url == "local"
            else call_server(args.base_url, payload)
        )
        print(f"Run {run_index + 1}/{args.runs}")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
