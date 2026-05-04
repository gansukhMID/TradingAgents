from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from tradingagents.agents.forex import (
    DebateAgent,
    ExecutionAgent,
    LiquidityAgent,
    MarketStructureAgent,
    RiskManagerAgent,
    SentimentAgent,
    SignalSynthesisAgent,
    TechnicalAgent,
)
from tradingagents.domain.schemas import (
    AnalyzeRequest,
    Candle,
    DebateReport,
    ExecutionSignal,
    ForexSignal,
    ForexSignalRequest,
    LiquidityReport,
    MarketBias,
    MarketStructureReport,
    RiskPlan,
    SentimentReport,
    SignalDirection,
    TechnicalReport,
)
from tradingagents.services.data import ForexDataService


class ForexGraphState(TypedDict, total=False):
    request: ForexSignalRequest
    analyze_request: AnalyzeRequest
    candles: list[Candle]
    market_structure: MarketStructureReport
    liquidity: LiquidityReport
    technicals: TechnicalReport
    sentiment: SentimentReport
    debate: DebateReport
    candidate_direction: SignalDirection
    candidate_bias: MarketBias
    candidate_confidence: float
    risk_plan: RiskPlan | None
    signal: ForexSignal
    execution: ExecutionSignal


class ForexSignalGraph:
    """LangGraph orchestration for the Forex multi-agent signal engine."""

    def __init__(self, data_service: ForexDataService | None = None):
        self.data_service = data_service or ForexDataService()
        self.market_structure_agent = MarketStructureAgent()
        self.liquidity_agent = LiquidityAgent()
        self.technical_agent = TechnicalAgent()
        self.sentiment_agent = SentimentAgent()
        self.debate_agent = DebateAgent()
        self.risk_agent = RiskManagerAgent()
        self.execution_agent = ExecutionAgent()
        self.synthesis_agent = SignalSynthesisAgent()
        self.workflow = self._build_signal_workflow()
        self.graph = self.workflow.compile()
        self.analyze_workflow = self._build_analyze_workflow()
        self.analyze_graph = self.analyze_workflow.compile()

    def analyze(self, request: ForexSignalRequest) -> ForexSignal:
        state = self.graph.invoke({"request": request})
        return state["signal"]

    def analyze_execution(self, request: AnalyzeRequest) -> ExecutionSignal:
        state = self.analyze_graph.invoke({"analyze_request": request})
        return state["execution"]

    def _build_signal_workflow(self) -> StateGraph:
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

    def _build_analyze_workflow(self) -> StateGraph:
        workflow = StateGraph(ForexGraphState)
        workflow.add_node("load_analyze_candles", self._load_analyze_candles)
        workflow.add_node("market_structure_agent", self._market_structure)
        workflow.add_node("technical_agent", self._technicals)
        workflow.add_node("sentiment_agent", self._sentiment)
        workflow.add_node("debate_agent", self._debate)
        workflow.add_node("risk_manager_agent", self._risk_manager)
        workflow.add_node("execution_agent", self._execution)

        workflow.add_edge(START, "load_analyze_candles")
        workflow.add_edge("load_analyze_candles", "market_structure_agent")
        workflow.add_edge("market_structure_agent", "technical_agent")
        workflow.add_edge("technical_agent", "sentiment_agent")
        workflow.add_edge("sentiment_agent", "debate_agent")
        workflow.add_edge("debate_agent", "risk_manager_agent")
        workflow.add_edge("risk_manager_agent", "execution_agent")
        workflow.add_edge("execution_agent", END)
        return workflow

    def _load_candles(self, state: ForexGraphState) -> dict[str, Any]:
        request = state["request"]
        candles = request.candles or self.data_service.get_candles(
            request.pair,
            request.timeframe,
            request.lookback,
        )
        return {"candles": candles[-request.lookback :]}

    def _load_analyze_candles(self, state: ForexGraphState) -> dict[str, Any]:
        request = state["analyze_request"]
        candles = request.ohlc or self.data_service.get_candles(
            request.symbol,
            request.timeframe,
            request.lookback,
        )
        return {
            "candles": candles[-request.lookback :],
            "analyze_request": request.model_copy(
                update={"lookback": min(request.lookback, len(candles))}
            ),
        }

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

    def _sentiment(self, state: ForexGraphState) -> dict[str, Any]:
        return {
            "sentiment": self.sentiment_agent.analyze(
                state["analyze_request"],
                state["market_structure"],
                state["technicals"],
            )
        }

    def _debate(self, state: ForexGraphState) -> dict[str, Any]:
        return {
            "debate": self.debate_agent.analyze(
                state["market_structure"],
                state["technicals"],
                state["sentiment"],
            )
        }

    def _risk_manager(self, state: ForexGraphState) -> dict[str, Any]:
        return {
            "risk_plan": self.risk_agent.plan(
                state["analyze_request"],
                state["debate"].direction,
                state["candles"],
                state["technicals"],
            )
        }

    def _execution(self, state: ForexGraphState) -> dict[str, Any]:
        return {
            "execution": self.execution_agent.execute(
                state["analyze_request"],
                state["debate"],
                state["risk_plan"],
                state["candles"],
            )
        }

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
