from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class MarketBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @field_validator("open", "high", "low", "close")
    @classmethod
    def price_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("OHLC prices must be positive")
        return value


class ForexSignalRequest(BaseModel):
    pair: str = Field(..., examples=["EURUSD"], description="Forex pair, with or without slash.")
    timeframe: Timeframe = Timeframe.H1
    candles: list[Candle] | None = Field(
        default=None,
        description="Optional OHLCV candles. If omitted, the service fetches recent FX candles.",
    )
    lookback: int = Field(default=160, ge=50, le=1000)
    account_equity: float = Field(default=10_000.0, gt=0)
    risk_per_trade: float = Field(default=0.01, gt=0, le=0.05)
    min_rr: float = Field(default=2.0, ge=1.0, le=10.0)

    @field_validator("pair")
    @classmethod
    def normalize_pair(cls, value: str) -> str:
        normalized = value.replace("/", "").replace("-", "").upper().strip()
        if len(normalized) != 6 or not normalized.isalpha():
            raise ValueError("pair must be a six-letter forex pair such as EURUSD")
        return normalized

    @field_validator("candles")
    @classmethod
    def require_enough_candles(cls, value: list[Candle] | None) -> list[Candle] | None:
        if value is not None and len(value) < 50:
            raise ValueError("at least 50 candles are required for analysis")
        return value


class AnalyzeRequest(BaseModel):
    symbol: str = Field(default="EURUSD", examples=["EURUSD"])
    timeframe: Timeframe = Timeframe.H1
    ohlc: list[Candle] | None = Field(
        default=None,
        description="Optional OHLCV candles. Dummy EURUSD-style candles are generated when omitted.",
    )
    lookback: int = Field(default=80, ge=30, le=1000)
    account_equity: float = Field(default=10_000.0, gt=0)
    risk_per_trade: float = Field(default=0.01, gt=0, le=0.05)
    min_rr: float = Field(default=2.0, ge=1.0, le=10.0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.replace("/", "").replace("-", "").upper().strip()
        if len(normalized) != 6 or not normalized.isalpha():
            raise ValueError("symbol must be a six-letter forex symbol such as EURUSD")
        return normalized

    @field_validator("ohlc")
    @classmethod
    def require_usable_ohlc(cls, value: list[Candle] | None) -> list[Candle] | None:
        if value is not None and len(value) < 30:
            raise ValueError("at least 30 OHLC candles are required when data is supplied")
        return value


class SwingPoint(BaseModel):
    index: int
    timestamp: datetime
    price: float
    kind: Literal["high", "low"]


class StructureBreak(BaseModel):
    index: int
    timestamp: datetime
    price: float
    kind: Literal["bos", "choch"]
    direction: MarketBias
    reference_price: float


class OrderBlock(BaseModel):
    start_index: int
    end_index: int
    high: float
    low: float
    direction: MarketBias
    mitigated: bool = False


class FairValueGap(BaseModel):
    index: int
    high: float
    low: float
    direction: MarketBias
    filled: bool = False


class MarketStructureReport(BaseModel):
    bias: MarketBias
    structure: Literal["BOS", "CHoCH", "range"]
    liquidity_sweep: bool
    key_levels: list[float]
    latest_close: float
    swing_highs: list[SwingPoint]
    swing_lows: list[SwingPoint]
    breaks: list[StructureBreak]
    order_blocks: list[OrderBlock]
    fair_value_gaps: list[FairValueGap]
    narrative: str


class LiquidityZone(BaseModel):
    kind: Literal["equal_highs", "equal_lows", "buy_side_sweep", "sell_side_sweep"]
    price: float
    strength: float = Field(ge=0, le=1)
    index: int
    timestamp: datetime
    swept: bool = False


class LiquidityReport(BaseModel):
    bias: MarketBias
    zones: list[LiquidityZone]
    nearest_buy_side: float | None = None
    nearest_sell_side: float | None = None
    narrative: str


class IndicatorSnapshot(BaseModel):
    ema_fast: float
    ema_slow: float
    rsi: float
    atr: float
    macd: float
    macd_signal: float
    macd_histogram: float
    average_range: float
    trend_bias: MarketBias
    momentum_bias: MarketBias


class TechnicalReport(BaseModel):
    indicators: IndicatorSnapshot
    support: float
    resistance: float
    narrative: str


class SentimentReport(BaseModel):
    score: float = Field(ge=-1, le=1)
    bias: MarketBias
    drivers: list[str]
    narrative: str


class DebateReport(BaseModel):
    direction: SignalDirection
    confidence: float = Field(ge=0, le=1)
    bias: MarketBias
    bullish_score: float = Field(ge=0, le=1)
    bearish_score: float = Field(ge=0, le=1)
    rationale: list[str]


class RiskPlan(BaseModel):
    entry: float
    stop_loss: float
    take_profit: float
    risk_reward: float
    risk_amount: float
    position_units: float
    lot_size: float = 0.0
    invalidation: str


class ExecutionSignal(BaseModel):
    symbol: str
    direction: SignalDirection
    confidence: float = Field(ge=0, le=1)
    entry: float
    sl: float
    tp: float
    lot_size: float


class ForexSignal(BaseModel):
    pair: str
    timeframe: Timeframe
    direction: SignalDirection
    confidence: float = Field(ge=0, le=1)
    bias: MarketBias
    risk_plan: RiskPlan | None
    rationale: list[str]
    market_structure: MarketStructureReport
    liquidity: LiquidityReport | None = None
    technicals: TechnicalReport
    sentiment: SentimentReport | None = None
    debate: DebateReport | None = None
    execution: ExecutionSignal | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
