from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from math import pi, sin
from typing import Any

from tradingagents.domain.schemas import Candle, Timeframe

logger = logging.getLogger(__name__)


_TIMEFRAME_MINUTES = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
    Timeframe.D1: 1440,
}

_MT5_TIMEFRAMES = {
    Timeframe.M1: "TIMEFRAME_M1",
    Timeframe.M5: "TIMEFRAME_M5",
    Timeframe.M15: "TIMEFRAME_M15",
    Timeframe.M30: "TIMEFRAME_M30",
    Timeframe.H1: "TIMEFRAME_H1",
    Timeframe.H4: "TIMEFRAME_H4",
    Timeframe.D1: "TIMEFRAME_D1",
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

    The primary source is a locally configured MetaTrader 5 terminal via the
    ``MetaTrader5`` Python package. If MT5 is unavailable or returns no rates,
    the deterministic fallback keeps the API runnable in local and CI
    environments.
    """

    def get_candles(self, pair: str, timeframe: Timeframe, lookback: int) -> list[Candle]:
        try:
            return self.get_mt5_candles(pair, timeframe, lookback)
        except Exception as exc:
            logger.warning("Falling back to mock candles for %s %s: %s", pair, timeframe.value, exc)
            return self.get_mock_candles(pair, timeframe, lookback)

    def get_mt5_candles(self, pair: str, timeframe: Timeframe, lookback: int) -> list[Candle]:
        """Fetch OHLC candles from MetaTrader 5 and convert them to Candle models."""
        try:
            import MetaTrader5 as mt5
        except ImportError as exc:
            raise RuntimeError("MetaTrader5 package is not installed") from exc

        initialized = False
        try:
            initialized = bool(mt5.initialize())
            if not initialized:
                error = mt5.last_error() if hasattr(mt5, "last_error") else "unknown error"
                raise RuntimeError(f"MetaTrader 5 initialization failed: {error}")

            mt5_timeframe = getattr(mt5, _MT5_TIMEFRAMES[timeframe])
            rates = mt5.copy_rates_from_pos(pair, mt5_timeframe, 0, lookback)
            if rates is None or len(rates) == 0:
                error = mt5.last_error() if hasattr(mt5, "last_error") else "no rates returned"
                raise RuntimeError(f"MetaTrader 5 returned no candles for {pair}: {error}")

            return [self._rate_to_candle(rate) for rate in rates]
        finally:
            if initialized and hasattr(mt5, "shutdown"):
                mt5.shutdown()

    def get_mock_candles(self, pair: str, timeframe: Timeframe, lookback: int) -> list[Candle]:
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

    def _rate_to_candle(self, rate: Any) -> Candle:
        names = getattr(getattr(rate, "dtype", None), "names", None) or ()
        timestamp = datetime.fromtimestamp(int(rate["time"]), tz=UTC)
        if "tick_volume" in names or (hasattr(rate, "__contains__") and "tick_volume" in rate):
            volume = float(rate["tick_volume"])
        elif "volume" in names or (hasattr(rate, "__contains__") and "volume" in rate):
            volume = float(rate["volume"])
        else:
            volume = 0.0
        return Candle(
            timestamp=timestamp,
            open=float(rate["open"]),
            high=float(rate["high"]),
            low=float(rate["low"]),
            close=float(rate["close"]),
            volume=volume,
        )
