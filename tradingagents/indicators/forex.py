from __future__ import annotations

from statistics import fmean

from tradingagents.domain.schemas import Candle, IndicatorSnapshot, MarketBias


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    ema_values = [values[0]]
    for value in values[1:]:
        ema_values.append((value - ema_values[-1]) * multiplier + ema_values[-1])
    return ema_values


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) <= period:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for previous, current in zip(closes[-period - 1 : -1], closes[-period:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = fmean(gains) if gains else 0.0
    avg_loss = fmean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges: list[float] = []
    for previous, current in zip(candles[-period - 1 : -1], candles[-period:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    return fmean(true_ranges) if true_ranges else 0.0


def calculate_indicator_snapshot(candles: list[Candle]) -> IndicatorSnapshot:
    closes = [candle.close for candle in candles]
    ranges = [candle.high - candle.low for candle in candles[-20:]]
    ema_fast_series = _ema(closes, 20)
    ema_slow_series = _ema(closes, 50)
    macd_series = [
        fast - slow for fast, slow in zip(_ema(closes, 12), _ema(closes, 26))
    ]
    macd_signal_series = _ema(macd_series, 9)

    ema_fast = ema_fast_series[-1]
    ema_slow = ema_slow_series[-1]
    rsi = _rsi(closes)
    macd = macd_series[-1] if macd_series else 0.0
    macd_signal = macd_signal_series[-1] if macd_signal_series else 0.0
    macd_histogram = macd - macd_signal

    if ema_fast > ema_slow and closes[-1] > ema_fast:
        trend_bias = MarketBias.BULLISH
    elif ema_fast < ema_slow and closes[-1] < ema_fast:
        trend_bias = MarketBias.BEARISH
    else:
        trend_bias = MarketBias.NEUTRAL

    if rsi > 55 and macd_histogram > 0:
        momentum_bias = MarketBias.BULLISH
    elif rsi < 45 and macd_histogram < 0:
        momentum_bias = MarketBias.BEARISH
    else:
        momentum_bias = MarketBias.NEUTRAL

    return IndicatorSnapshot(
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        rsi=rsi,
        atr=_atr(candles),
        macd=macd,
        macd_signal=macd_signal,
        macd_histogram=macd_histogram,
        average_range=fmean(ranges) if ranges else 0.0,
        trend_bias=trend_bias,
        momentum_bias=momentum_bias,
    )
