from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import pi, sin

from tradingagents.domain.schemas import Candle, Timeframe


_TIMEFRAME_MINUTES = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
}

_PAIR_BASELINES = {
    "EURUSD": 1.0850,
    "GBPUSD": 1.2650,
    "USDJPY": 155.00,
    "AUDUSD": 0.6600,
    "USDCAD": 1.3650,
    "USDCHF": 0.9100,
    "NZDUSD": 0.6000,
}


class ForexDataService:
    """Provides candle data for the backend.

    Production deployments should swap this adapter for a broker or market-data
    provider. The deterministic fallback keeps the API runnable in local and CI
    environments without stock-specific yfinance dependencies.
    """

    def get_candles(self, pair: str, timeframe: Timeframe, lookback: int) -> list[Candle]:
        baseline = _PAIR_BASELINES.get(pair, 1.0)
        interval = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
        start = datetime.now(UTC) - interval * lookback
        candles: list[Candle] = []
        previous_close = baseline
        pip = 0.01 if pair.endswith("JPY") else 0.0001

        for index in range(lookback):
            timestamp = start + interval * index
            trend = (index / lookback - 0.5) * pip * 18
            cycle = sin(index / 9 * pi) * pip * 8
            close = baseline + trend + cycle
            open_price = previous_close
            wick = pip * (6 + abs(sin(index)) * 4)
            high = max(open_price, close) + wick
            low = min(open_price, close) - wick
            candles.append(
                Candle(
                    timestamp=timestamp,
                    open=round(open_price, 5),
                    high=round(high, 5),
                    low=round(low, 5),
                    close=round(close, 5),
                    volume=1_000 + index * 3,
                )
            )
            previous_close = close

        return candles
