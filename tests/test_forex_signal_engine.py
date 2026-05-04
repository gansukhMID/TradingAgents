from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tradingagents.api.app import app
from tradingagents.domain.schemas import AnalyzeRequest, ForexSignalRequest, SignalDirection
from tradingagents.graph import ForexSignalGraph


def _candles(count: int = 80) -> list[dict]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = []
    close = 1.1000
    for index in range(count):
        open_price = close
        close = open_price + 0.00015
        candles.append(
            {
                "timestamp": (start + timedelta(hours=index)).isoformat(),
                "open": open_price,
                "high": max(open_price, close) + 0.0004,
                "low": min(open_price, close) - 0.0004,
                "close": close,
                "volume": 1000,
            }
        )
    return candles


def test_forex_graph_returns_structured_signal() -> None:
    request = ForexSignalRequest(pair="EUR/USD", lookback=80)
    signal = ForexSignalGraph().analyze(request)

    assert signal.pair == "EURUSD"
    assert signal.direction in SignalDirection
    assert signal.market_structure.latest_close > 0
    assert signal.technicals.indicators.atr >= 0


def test_signal_endpoint_accepts_candles() -> None:
    client = TestClient(app)
    response = client.post(
        "/signals",
        json={
            "pair": "GBPUSD",
            "timeframe": "1h",
            "candles": _candles(),
            "lookback": 80,
            "account_equity": 25000,
            "risk_per_trade": 0.01,
            "min_rr": 1.5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["pair"] == "GBPUSD"
    assert payload["market_structure"]["latest_close"] > 0
    assert payload["technicals"]["indicators"]["atr"] >= 0


def test_analyze_endpoint_returns_execution_json() -> None:
    client = TestClient(app)
    response = client.post(
        "/analyze",
        json={
            "symbol": "EURUSD",
            "ohlc": _candles(),
            "account_equity": 10_000,
            "risk_per_trade": 0.01,
            "min_rr": 2.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"symbol", "direction", "confidence", "entry", "sl", "tp", "lot_size"}
    assert payload["symbol"] == "EURUSD"
    assert payload["direction"] in {"BUY", "SELL", "HOLD"}
    assert 0 <= payload["confidence"] <= 1
    assert payload["entry"] > 0


def test_analyze_graph_uses_dummy_data_when_ohlc_missing() -> None:
    signal = ForexSignalGraph().analyze_execution(AnalyzeRequest(symbol="EURUSD"))

    assert signal.symbol == "EURUSD"
    assert signal.direction in SignalDirection
    assert signal.entry > 0
