from __future__ import annotations

from fastapi import FastAPI

from tradingagents.domain.schemas import (
    AnalyzeRequest,
    ExecutionSignal,
    ForexSignal,
    ForexSignalRequest,
    HealthResponse,
)
from tradingagents.graph import ForexSignalGraph


def create_app() -> FastAPI:
    app = FastAPI(
        title="Forex AI Signal Engine",
        description="ICT/SMC multi-agent Forex signal backend powered by LangGraph.",
        version="1.0.0",
    )
    graph = ForexSignalGraph()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", service="forex-ai-signal-engine", version="1.0.0")

    @app.post("/signals", response_model=ForexSignal)
    def create_signal(request: ForexSignalRequest) -> ForexSignal:
        return graph.analyze(request)

    @app.post("/analyze", response_model=ExecutionSignal)
    def analyze(request: AnalyzeRequest) -> ExecutionSignal:
        return graph.analyze_execution(request)

    return app


app = create_app()
