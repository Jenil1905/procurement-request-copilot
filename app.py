"""FastAPI web application for AI Procurement Request Copilot.

Serves:
1. Single-page HTML/JS product UI.
2. API endpoints for executing Architecture A / B copilot analysis.
3. Human-in-the-loop audit log endpoint (logs decisions to data/decisions_log.jsonl).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.contracts import ProcurementDecision
from src.solution import run

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
STATIC_DIR = ROOT / "static"
DECISIONS_LOG_PATH = DATA_DIR / "decisions_log.jsonl"

app = FastAPI(
    title="AI Procurement Request Copilot",
    description="FastAPI service and UI for Procurement Evaluation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequestPayload(BaseModel):
    request_id: str | None = None
    request_data: dict[str, Any] | None = None
    arch: str = "A"
    simulate_vendor_down: bool = False


class HumanDecisionPayload(BaseModel):
    request_id: str
    action: str = Field(description="approve | reject | request_info")
    notes: str = ""
    approver: str = "Procurement Specialist"


@app.get("/", response_class=HTMLResponse)
def index_page() -> str:
    """Serves the single-page HTML frontend."""
    html_path = STATIC_DIR / "index.html"
    if not html_path.is_file():
        raise HTTPException(status_code=404, detail="static/index.html not found")
    return html_path.read_text(encoding="utf-8")


@app.get("/api/requests")
def list_requests() -> list[dict[str, Any]]:
    """Returns the synthetic requests dataset for the request picker."""
    req_path = DATA_DIR / "requests.json"
    if not req_path.is_file():
        return []
    return json.loads(req_path.read_text(encoding="utf-8"))


@app.post("/api/run", response_model=ProcurementDecision)
def execute_copilot(payload: RunRequestPayload) -> ProcurementDecision:
    """Executes the Procurement Copilot pipeline across Architecture A or B."""
    target = payload.request_data if payload.request_data else (payload.request_id or "REQ-1001")
    try:
        decision = run(
            target,
            arch=payload.arch,
            simulate_vendor_down=payload.simulate_vendor_down,
        )
        return decision
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Copilot execution failed: {type(exc).__name__}: {exc}")


@app.post("/api/human-decision")
def record_human_decision(payload: HumanDecisionPayload) -> dict[str, Any]:
    """Records a human decision in data/decisions_log.jsonl without making an autonomous purchase."""
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
        "timestamp": timestamp,
        "request_id": payload.request_id,
        "action": payload.action,
        "notes": payload.notes,
        "approver": payload.approver,
    }
    with DECISIONS_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return {
        "ok": True,
        "timestamp": timestamp,
        "message": f"Human decision '{payload.action}' recorded for {payload.request_id}",
    }


@app.get("/api/decisions-log")
def get_decisions_log() -> list[dict[str, Any]]:
    """Returns the audit log of all human decisions."""
    if not DECISIONS_LOG_PATH.is_file():
        return []
    entries = []
    with DECISIONS_LOG_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Procurement Copilot App"}
