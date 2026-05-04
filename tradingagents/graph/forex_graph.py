from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from tradingagents.agents.forex import (
    LiquidityAgent,
    MarketStructureAgent,
    RiskManagementAgent,
    SignalSynthesisAgent,
    TechnicalAnalysisAgent,
)
from tradingagents.domain.schemas import (
    Candle,
    ForexSignal,
    ForexSignalRequest,
    LiquidityReport,
    MarketBias,
    MarketStructureReport,
    RiskPlan,
    SignalDirection,
    TechnicalReport,
)
from tradingagents.services.data import ForexDataService


class ForexGraphState(TypedDict, total=False):
    request: ForexSignalRequest
    candles: list[Candle]
    market_structure: MarketStructureReport
    liquidity: LiquidityReport
    technicals: TechnicalReport
    candidate_direction: SignalDirection
    candidate_bias: MarketBias
    candidate_confidence: float
    risk_plan: RiskPlan | None
    signal: ForexSignal


class ForexSignalGraph:
    """LangGraph orchestration for the Forex multi-agent signal engine."""

    def __init__(self, data_service: ForexDataService | None = None):
        self.data_service = data_service or ForexDataService()
        self.market_structure_agent = MarketStructureAgent()
        self.liquidity_agent = LiquidityAgent()
        self.technical_agent = TechnicalAnalysisAgent()
        self.risk_agent = RiskManagementAgent()
        self.synthesis_agent = SignalSynthesisAgent()
        self.workflow = self._build_workflow()
        self.graph = self.workflow.compile()

    def analyze(self, request: ForexSignalRequest) -> ForexSignal:
        state = self.graph.invoke({"request": request})
        return state["signal"]

    def _build_workflow(self) -> StateGraph:
        workflow = StateGraph(ForexGraphState)
        workflow.add_node("load_candles", self._load_candles)
        workflow.add_node("market_structure", self._market_structure)
        workflow.add_node("liquidity", self._liquidity)
        workflow.add_node("technicals", self._technicals)
        workflow.add_node("directional_confluence", self._directional_confluence)
        workflow.add_node("risk_management", self._risk_management)
        workflow.add_node("signal_synthesis", self._signal_synthesis)

        workflow.add_edge(START, "load_candles")
        workflow.add_edge("load_candles", "market_structure")
        workflow.add_edge("market_structure", "liquidity")
        workflow.add_edge("liquidity", "technicals")
        workflow.add_edge("technicals", "directional_confluence")
        workflow.add_edge("directional_confluence", "risk_management")
        workflow.add_edge("risk_management", "signal_synthesis")
        workflow.add_edge("signal_synthesis", END)
        return workflow

    def _load_candles(self, state: ForexGraphState) -> dict[str, Any]:
        request = state["request"]
        candles = request.candles or self.data_service.get_candles(
            request.pair,
            request.timeframe,
            request.lookback,
        )
        return {"candles": candles[-request.lookback :]}

    def _market_structure(self, state: ForexGraphState) -> dict[str, Any]:
        return {"market_structure": self.market_structure_agent.analyze(state["candles"])}

    def _liquidity(self, state: ForexGraphState) -> dict[str, Any]:
        return {
            "liquidity": self.liquidity_agent.analyze(
                state["candles"],
                state["market_structure"],
            )
        }

    def _technicals(self, state: ForexGraphState) -> dict[str, Any]:
        return {"technicals": self.technical_agent.analyze(state["candles"])}

    def _directional_confluence(self, state: ForexGraphState) -> dict[str, Any]:
        direction, bias, confidence = self.synthesis_agent.decide_direction(
            state["market_structure"],
            state["liquidity"],
            state["technicals"],
        )
        return {
            "candidate_direction": direction,
            "candidate_bias": bias,
            "candidate_confidence": confidence,
        }

    def _risk_management(self, state: ForexGraphState) -> dict[str, Any]:
        return {
            "risk_plan": self.risk_agent.plan(
                state["request"],
                state["candidate_direction"],
                state["candles"],
                state["technicals"],
                state["liquidity"],
            )
        }

    def _signal_synthesis(self, state: ForexGraphState) -> dict[str, Any]:
        return {
            "signal": self.synthesis_agent.synthesize(
                state["request"],
                state["market_structure"],
                state["liquidity"],
                state["technicals"],
                state["risk_plan"],
            )
        }
