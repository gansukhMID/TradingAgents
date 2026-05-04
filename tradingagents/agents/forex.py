from __future__ import annotations

from collections import Counter

from tradingagents.domain.schemas import (
    AnalyzeRequest,
    Candle,
    DebateReport,
    ExecutionSignal,
    FairValueGap,
    ForexSignal,
    ForexSignalRequest,
    LiquidityReport,
    LiquidityZone,
    MarketBias,
    MarketStructureReport,
    OrderBlock,
    RiskPlan,
    SentimentReport,
    SignalDirection,
    StructureBreak,
    SwingPoint,
    TechnicalReport,
)
from tradingagents.indicators.forex import calculate_indicator_snapshot


class MarketStructureAgent:
    """Detect ICT/SMC market structure without collapsing logic into an LLM call."""

    def analyze(self, candles: list[Candle]) -> MarketStructureReport:
        swing_highs, swing_lows = self._find_swings(candles)
        breaks = self._find_breaks(candles, swing_highs, swing_lows)
        order_blocks = self._find_order_blocks(candles, breaks)
        fair_value_gaps = self._find_fair_value_gaps(candles)
        bias = self._derive_bias(candles, breaks, swing_highs, swing_lows)

        return MarketStructureReport(
            bias=bias,
            latest_close=candles[-1].close,
            swing_highs=swing_highs[-12:],
            swing_lows=swing_lows[-12:],
            breaks=breaks[-8:],
            order_blocks=order_blocks[-6:],
            fair_value_gaps=fair_value_gaps[-8:],
            narrative=self._narrative(bias, breaks, order_blocks, fair_value_gaps),
        )

    def _find_swings(self, candles: list[Candle], width: int = 2) -> tuple[list[SwingPoint], list[SwingPoint]]:
        highs: list[SwingPoint] = []
        lows: list[SwingPoint] = []
        for index in range(width, len(candles) - width):
            window = candles[index - width : index + width + 1]
            current = candles[index]
            if current.high == max(candle.high for candle in window):
                highs.append(
                    SwingPoint(index=index, timestamp=current.timestamp, price=current.high, kind="high")
                )
            if current.low == min(candle.low for candle in window):
                lows.append(
                    SwingPoint(index=index, timestamp=current.timestamp, price=current.low, kind="low")
                )
        return highs, lows

    def _find_breaks(
        self,
        candles: list[Candle],
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> list[StructureBreak]:
        breaks: list[StructureBreak] = []
        for index, candle in enumerate(candles):
            prior_highs = [swing for swing in swing_highs if swing.index < index]
            prior_lows = [swing for swing in swing_lows if swing.index < index]
            if prior_highs and candle.close > prior_highs[-1].price:
                breaks.append(
                    StructureBreak(
                        index=index,
                        timestamp=candle.timestamp,
                        price=candle.close,
                        kind="bos" if not breaks or breaks[-1].direction == MarketBias.BULLISH else "choch",
                        direction=MarketBias.BULLISH,
                        reference_price=prior_highs[-1].price,
                    )
                )
            if prior_lows and candle.close < prior_lows[-1].price:
                breaks.append(
                    StructureBreak(
                        index=index,
                        timestamp=candle.timestamp,
                        price=candle.close,
                        kind="bos" if not breaks or breaks[-1].direction == MarketBias.BEARISH else "choch",
                        direction=MarketBias.BEARISH,
                        reference_price=prior_lows[-1].price,
                    )
                )
        return breaks

    def _find_order_blocks(
        self, candles: list[Candle], breaks: list[StructureBreak]
    ) -> list[OrderBlock]:
        blocks: list[OrderBlock] = []
        for break_event in breaks[-12:]:
            search_start = max(0, break_event.index - 8)
            origin: int | None = None
            if break_event.direction == MarketBias.BULLISH:
                for idx in range(break_event.index - 1, search_start - 1, -1):
                    if candles[idx].close < candles[idx].open:
                        origin = idx
                        break
            else:
                for idx in range(break_event.index - 1, search_start - 1, -1):
                    if candles[idx].close > candles[idx].open:
                        origin = idx
                        break
            if origin is None:
                continue
            block = candles[origin]
            mitigated = any(
                future.low <= block.high and future.high >= block.low
                for future in candles[break_event.index + 1 :]
            )
            blocks.append(
                OrderBlock(
                    start_index=origin,
                    end_index=origin,
                    high=block.high,
                    low=block.low,
                    direction=break_event.direction,
                    mitigated=mitigated,
                )
            )
        return blocks

    def _find_fair_value_gaps(self, candles: list[Candle]) -> list[FairValueGap]:
        gaps: list[FairValueGap] = []
        for index in range(2, len(candles)):
            previous = candles[index - 2]
            current = candles[index]
            if current.low > previous.high:
                gaps.append(
                    FairValueGap(
                        index=index - 1,
                        high=current.low,
                        low=previous.high,
                        direction=MarketBias.BULLISH,
                        filled=any(candle.low <= previous.high for candle in candles[index + 1 :]),
                    )
                )
            if current.high < previous.low:
                gaps.append(
                    FairValueGap(
                        index=index - 1,
                        high=previous.low,
                        low=current.high,
                        direction=MarketBias.BEARISH,
                        filled=any(candle.high >= previous.low for candle in candles[index + 1 :]),
                    )
                )
        return gaps

    def _derive_bias(
        self,
        candles: list[Candle],
        breaks: list[StructureBreak],
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> MarketBias:
        if breaks:
            recent = breaks[-3:]
            counts = Counter(item.direction for item in recent)
            if counts[MarketBias.BULLISH] > counts[MarketBias.BEARISH]:
                return MarketBias.BULLISH
            if counts[MarketBias.BEARISH] > counts[MarketBias.BULLISH]:
                return MarketBias.BEARISH
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            higher_high = swing_highs[-1].price > swing_highs[-2].price
            higher_low = swing_lows[-1].price > swing_lows[-2].price
            lower_high = swing_highs[-1].price < swing_highs[-2].price
            lower_low = swing_lows[-1].price < swing_lows[-2].price
            if higher_high and higher_low:
                return MarketBias.BULLISH
            if lower_high and lower_low:
                return MarketBias.BEARISH
        if candles[-1].close > candles[0].close:
            return MarketBias.BULLISH
        if candles[-1].close < candles[0].close:
            return MarketBias.BEARISH
        return MarketBias.NEUTRAL

    def _narrative(
        self,
        bias: MarketBias,
        breaks: list[StructureBreak],
        order_blocks: list[OrderBlock],
        gaps: list[FairValueGap],
    ) -> str:
        return (
            f"Market structure bias is {bias.value}. "
            f"Detected {len(breaks)} structure breaks, {len(order_blocks)} order blocks, "
            f"and {len(gaps)} fair value gaps in the analysis window."
        )


class LiquidityAgent:
    def analyze(self, candles: list[Candle], structure: MarketStructureReport) -> LiquidityReport:
        zones: list[LiquidityZone] = []
        tolerance = self._price_tolerance(candles)

        for first, second in zip(structure.swing_highs, structure.swing_highs[1:]):
            if abs(first.price - second.price) <= tolerance:
                swept = any(candle.high > max(first.price, second.price) for candle in candles[second.index + 1 :])
                zones.append(
                    LiquidityZone(
                        kind="equal_highs",
                        price=(first.price + second.price) / 2,
                        strength=0.7,
                        index=second.index,
                        timestamp=second.timestamp,
                        swept=swept,
                    )
                )

        for first, second in zip(structure.swing_lows, structure.swing_lows[1:]):
            if abs(first.price - second.price) <= tolerance:
                swept = any(candle.low < min(first.price, second.price) for candle in candles[second.index + 1 :])
                zones.append(
                    LiquidityZone(
                        kind="equal_lows",
                        price=(first.price + second.price) / 2,
                        strength=0.7,
                        index=second.index,
                        timestamp=second.timestamp,
                        swept=swept,
                    )
                )

        zones.extend(self._sweeps(candles, structure.swing_highs, structure.swing_lows))
        close = candles[-1].close
        buy_side = [zone.price for zone in zones if zone.price > close and "high" in zone.kind]
        sell_side = [zone.price for zone in zones if zone.price < close and "low" in zone.kind]

        swept_buy = any(zone.kind == "buy_side_sweep" for zone in zones[-5:])
        swept_sell = any(zone.kind == "sell_side_sweep" for zone in zones[-5:])
        if swept_sell and structure.bias == MarketBias.BULLISH:
            bias = MarketBias.BULLISH
        elif swept_buy and structure.bias == MarketBias.BEARISH:
            bias = MarketBias.BEARISH
        else:
            bias = structure.bias

        return LiquidityReport(
            bias=bias,
            zones=zones[-12:],
            nearest_buy_side=min(buy_side) if buy_side else None,
            nearest_sell_side=max(sell_side) if sell_side else None,
            narrative=(
                f"Liquidity bias is {bias.value}; tracked {len(zones)} liquidity pools/sweeps "
                "around recent swing highs and lows."
            ),
        )

    def _price_tolerance(self, candles: list[Candle]) -> float:
        average_range = sum(candle.high - candle.low for candle in candles[-20:]) / min(20, len(candles))
        return average_range * 0.25

    def _sweeps(
        self,
        candles: list[Candle],
        swing_highs: list[SwingPoint],
        swing_lows: list[SwingPoint],
    ) -> list[LiquidityZone]:
        zones: list[LiquidityZone] = []
        for index, candle in enumerate(candles[-30:], start=max(0, len(candles) - 30)):
            prior_highs = [swing for swing in swing_highs if swing.index < index]
            prior_lows = [swing for swing in swing_lows if swing.index < index]
            if prior_highs and candle.high > prior_highs[-1].price and candle.close < prior_highs[-1].price:
                zones.append(
                    LiquidityZone(
                        kind="buy_side_sweep",
                        price=prior_highs[-1].price,
                        strength=0.9,
                        index=index,
                        timestamp=candle.timestamp,
                        swept=True,
                    )
                )
            if prior_lows and candle.low < prior_lows[-1].price and candle.close > prior_lows[-1].price:
                zones.append(
                    LiquidityZone(
                        kind="sell_side_sweep",
                        price=prior_lows[-1].price,
                        strength=0.9,
                        index=index,
                        timestamp=candle.timestamp,
                        swept=True,
                    )
                )
        return zones


class TechnicalAgent:
    def analyze(self, candles: list[Candle]) -> TechnicalReport:
        indicators = calculate_indicator_snapshot(candles)
        recent = candles[-30:]
        support = min(candle.low for candle in recent)
        resistance = max(candle.high for candle in recent)
        return TechnicalReport(
            indicators=indicators,
            support=support,
            resistance=resistance,
            narrative=(
                f"Trend bias is {indicators.trend_bias.value}; momentum bias is "
                f"{indicators.momentum_bias.value}; ATR is {indicators.atr:.5f}."
            ),
        )


TechnicalAnalysisAgent = TechnicalAgent


class SentimentAgent:
    """Deterministic macro/session sentiment proxy for runnable local analysis."""

    def analyze(self, request: AnalyzeRequest, structure: MarketStructureReport, technicals: TechnicalReport) -> SentimentReport:
        score = 0.0
        drivers: list[str] = []

        if structure.bias == MarketBias.BULLISH:
            score += 0.25
            drivers.append("market structure is bullish")
        elif structure.bias == MarketBias.BEARISH:
            score -= 0.25
            drivers.append("market structure is bearish")

        if technicals.indicators.momentum_bias == MarketBias.BULLISH:
            score += 0.2
            drivers.append("momentum confirms upside")
        elif technicals.indicators.momentum_bias == MarketBias.BEARISH:
            score -= 0.2
            drivers.append("momentum confirms downside")

        symbol_factor = (sum(ord(char) for char in request.symbol) % 9 - 4) / 100
        score += symbol_factor
        drivers.append("mock macro sentiment is neutral-to-directional from symbol seed")
        score = max(-1.0, min(1.0, score))

        if score > 0.15:
            bias = MarketBias.BULLISH
        elif score < -0.15:
            bias = MarketBias.BEARISH
        else:
            bias = MarketBias.NEUTRAL

        return SentimentReport(
            bias=bias,
            score=round(score, 4),
            drivers=drivers,
            narrative=f"Sentiment bias is {bias.value} with score {score:.2f}.",
        )


class DebateAgent:
    def analyze(
        self,
        structure: MarketStructureReport,
        technicals: TechnicalReport,
        sentiment: SentimentReport,
    ) -> DebateReport:
        votes = [structure.bias, technicals.indicators.trend_bias, technicals.indicators.momentum_bias, sentiment.bias]
        bullish_votes = votes.count(MarketBias.BULLISH)
        bearish_votes = votes.count(MarketBias.BEARISH)

        if bullish_votes > bearish_votes and bullish_votes >= 2:
            direction = SignalDirection.BUY
            bias = MarketBias.BULLISH
            confidence = bullish_votes / len(votes)
        elif bearish_votes > bullish_votes and bearish_votes >= 2:
            direction = SignalDirection.SELL
            bias = MarketBias.BEARISH
            confidence = bearish_votes / len(votes)
        else:
            direction = SignalDirection.HOLD
            bias = MarketBias.NEUTRAL
            confidence = 0.5

        bull_case = [
            "Bullish structure supports longs." if structure.bias == MarketBias.BULLISH else "No bullish structure edge.",
            "Technical momentum supports longs." if technicals.indicators.momentum_bias == MarketBias.BULLISH else "Momentum is not bullish.",
        ]
        bear_case = [
            "Bearish structure supports shorts." if structure.bias == MarketBias.BEARISH else "No bearish structure edge.",
            "Technical momentum supports shorts." if technicals.indicators.momentum_bias == MarketBias.BEARISH else "Momentum is not bearish.",
        ]

        bullish_score = bullish_votes / len(votes)
        bearish_score = bearish_votes / len(votes)
        return DebateReport(
            direction=direction,
            confidence=round(confidence, 4),
            bias=bias,
            bullish_score=round(bullish_score, 4),
            bearish_score=round(bearish_score, 4),
            rationale=[
                *bull_case,
                *bear_case,
                f"Debate selected {direction.value} with {confidence:.0%} agent confluence.",
            ],
        )


class RiskManagerAgent:
    def plan(
        self,
        request: ForexSignalRequest | AnalyzeRequest,
        direction: SignalDirection,
        candles: list[Candle],
        technicals: TechnicalReport,
        liquidity: LiquidityReport | None = None,
    ) -> RiskPlan | None:
        if direction == SignalDirection.HOLD:
            return None

        entry = candles[-1].close
        atr = max(technicals.indicators.atr, technicals.indicators.average_range, entry * 0.0005)
        if direction == SignalDirection.BUY:
            structural_stop = liquidity.nearest_sell_side if liquidity else technicals.support
            structural_stop = structural_stop or technicals.support
            stop_loss = min(entry - atr, structural_stop - atr * 0.15)
            take_profit = entry + max(request.min_rr * (entry - stop_loss), atr)
        else:
            structural_stop = liquidity.nearest_buy_side if liquidity else technicals.resistance
            structural_stop = structural_stop or technicals.resistance
            stop_loss = max(entry + atr, structural_stop + atr * 0.15)
            take_profit = entry - max(request.min_rr * (stop_loss - entry), atr)

        risk_per_unit = abs(entry - stop_loss)
        risk_amount = request.account_equity * request.risk_per_trade
        position_units = risk_amount / risk_per_unit if risk_per_unit else 0.0
        lot_size = max(0.01, min(100.0, position_units / 100_000))
        reward = abs(take_profit - entry)
        risk_reward = reward / risk_per_unit if risk_per_unit else 0.0

        if risk_reward < request.min_rr:
            return None

        return RiskPlan(
            entry=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            risk_amount=risk_amount,
            position_units=position_units,
            lot_size=lot_size,
            invalidation=(
                "Bullish setup invalidates below stop loss and failed reclaim of discount zone."
                if direction == SignalDirection.BUY
                else "Bearish setup invalidates above stop loss and failed rejection of premium zone."
            ),
        )


RiskManagementAgent = RiskManagerAgent


class ExecutionAgent:
    def execute(
        self,
        request: AnalyzeRequest,
        debate: DebateReport,
        risk_plan: RiskPlan | None,
        candles: list[Candle],
    ) -> ExecutionSignal:
        entry = risk_plan.entry if risk_plan else candles[-1].close
        if risk_plan:
            stop_loss = risk_plan.stop_loss
            take_profit = risk_plan.take_profit
            lot_size = risk_plan.lot_size
        else:
            pip = 0.01 if request.symbol.endswith("JPY") else 0.0001
            stop_loss = entry - 30 * pip
            take_profit = entry + 70 * pip
            lot_size = 0.0

        direction = debate.direction
        confidence = debate.confidence
        if risk_plan is None and direction != SignalDirection.HOLD:
            direction = SignalDirection.HOLD
            confidence = min(confidence, 0.5)

        return ExecutionSignal(
            symbol=request.symbol,
            direction=direction,
            confidence=round(confidence, 4),
            entry=round(entry, 5),
            sl=round(stop_loss, 5),
            tp=round(take_profit, 5),
            lot_size=round(lot_size, 2),
        )


class SignalSynthesisAgent:
    def decide_direction(
        self,
        structure: MarketStructureReport,
        liquidity: LiquidityReport,
        technicals: TechnicalReport,
    ) -> tuple[SignalDirection, MarketBias, float]:
        votes = [
            structure.bias,
            liquidity.bias,
            technicals.indicators.trend_bias,
            technicals.indicators.momentum_bias,
        ]
        bullish_votes = votes.count(MarketBias.BULLISH)
        bearish_votes = votes.count(MarketBias.BEARISH)

        if bullish_votes >= 3:
            return SignalDirection.BUY, MarketBias.BULLISH, bullish_votes / len(votes)
        if bearish_votes >= 3:
            return SignalDirection.SELL, MarketBias.BEARISH, bearish_votes / len(votes)
        return SignalDirection.HOLD, MarketBias.NEUTRAL, max(bullish_votes, bearish_votes) / len(votes)

    def synthesize(
        self,
        request: ForexSignalRequest,
        structure: MarketStructureReport,
        liquidity: LiquidityReport,
        technicals: TechnicalReport,
        risk_plan: RiskPlan | None,
    ) -> ForexSignal:
        direction, bias, agreement = self.decide_direction(structure, liquidity, technicals)

        if risk_plan is None and direction != SignalDirection.HOLD:
            direction = SignalDirection.HOLD
            bias = MarketBias.NEUTRAL

        confidence = agreement
        if risk_plan:
            confidence = min(0.95, confidence + min(0.2, (risk_plan.risk_reward - request.min_rr) * 0.05))
        if direction == SignalDirection.HOLD:
            confidence = min(confidence, 0.55)

        rationale = [
            structure.narrative,
            liquidity.narrative,
            technicals.narrative,
            "Risk plan accepted." if risk_plan else "No trade until directional confluence and risk/reward align.",
        ]

        return ForexSignal(
            pair=request.pair,
            timeframe=request.timeframe,
            direction=direction,
            confidence=round(confidence, 4),
            bias=bias,
            risk_plan=risk_plan,
            rationale=rationale,
            market_structure=structure,
            liquidity=liquidity,
            technicals=technicals,
            metadata={"engine": "forex-ai-signal-engine", "workflow": "langgraph"},
        )
