"""
AIL UI API — FastAPI backend for pipeline visualization.

Endpoints:
  GET  /api/status          — system overview
  GET  /api/tasks           — list tasks across stages
  GET  /api/tasks/{id}      — single task details
  GET  /api/manifests       — list execution manifests
  GET  /api/manifests/{id}  — single manifest
  GET  /api/memory          — agent memory summary
  GET  /api/memory/recall   — recall similar past tasks
  GET  /api/agents          — agent states
  GET  /api/logs            — recent log entries
  POST /api/tasks           — submit a new goal

Static files served from ui/static/
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.agent_memory import AgentMemory
from core.manifest import list_manifests, load_manifest
from core.memory import load_agents_state, load_routing_state

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
TASKS_DIR = BASE_DIR / "tasks"
MANIFESTS_DIR = BASE_DIR / "manifests"
LOGS_DIR = BASE_DIR / "logs"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="AIL Pipeline Dashboard",
    description="Visualization and management for the AIL execution pipeline",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

memory = AgentMemory()
memory.rebuild()


class GoalRequest(BaseModel):
    goal: str
    repo: str = "."
    constraints: list[str] = []


@app.get("/", response_class=HTMLResponse)
async def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return index.read_text(encoding="utf-8")
    return HTMLResponse("<h1>AIL Dashboard</h1><p>static/index.html not found</p>")


@app.get("/api/status")
async def get_status():
    task_counts = {}
    for stage in ("incoming", "running", "done", "failed"):
        stage_dir = TASKS_DIR / stage
        if stage_dir.exists():
            task_counts[stage] = len(list(stage_dir.glob("*.json")))
        else:
            task_counts[stage] = 0

    manifest_count = len(list(MANIFESTS_DIR.glob("*.manifest.json"))) if MANIFESTS_DIR.exists() else 0

    agents_state = load_agents_state()
    routing_state = load_routing_state()

    return {
        "system": "AIL — Assistant Instruction Layer",
        "version": "1.0.0",
        "pipeline_stages": ["incoming", "running", "validating", "done", "failed"],
        "task_counts": task_counts,
        "manifest_count": manifest_count,
        "memory_entries": len(memory.entries),
        "agents": agents_state.get("agents", {}),
        "last_routing": routing_state.get("last_decision"),
    }


@app.get("/api/tasks")
async def list_tasks(stage: str = Query(default="", description="Filter by stage")):
    tasks: list[dict[str, Any]] = []
    stages = [stage] if stage else ["incoming", "running", "done", "failed"]

    for s in stages:
        stage_dir = TASKS_DIR / s
        if not stage_dir.exists():
            continue
        for path in sorted(stage_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["_stage"] = s
                tasks.append(data)
            except (json.JSONDecodeError, OSError):
                continue

    return {"tasks": tasks, "count": len(tasks)}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    for stage in ("incoming", "running", "done", "failed"):
        path = TASKS_DIR / stage / f"{task_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                data["_stage"] = stage
                return data
            except (json.JSONDecodeError, OSError):
                pass
    raise HTTPException(status_code=404, detail=f"Task {task_id} not found")


@app.get("/api/manifests")
async def get_manifests(limit: int = Query(default=20, ge=1, le=100)):
    manifest_ids = list_manifests()
    items: list[dict[str, Any]] = []

    for mid in manifest_ids[-limit:]:
        m = load_manifest(mid)
        if m:
            items.append(m.to_dict())

    items.reverse()
    return {"manifests": items, "count": len(items)}


@app.get("/api/manifests/{manifest_id}")
async def get_manifest(manifest_id: str):
    m = load_manifest(manifest_id)
    if not m:
        raise HTTPException(status_code=404, detail=f"Manifest {manifest_id} not found")
    return m.to_dict()


@app.get("/api/memory")
async def get_memory():
    return {
        "entries_count": len(memory.entries),
        "success_patterns": memory.get_success_patterns()[:10],
        "error_patterns": memory.get_error_patterns()[:10],
    }


@app.get("/api/memory/recall")
async def recall_memory(goal: str = Query(..., description="Goal to recall")):
    results = memory.recall(goal, top_k=5)
    return {"goal": goal, "matches": results}


@app.get("/api/agents")
async def get_agents():
    state = load_agents_state()
    return state.get("agents", {})


@app.get("/api/logs")
async def get_logs(limit: int = Query(default=50, ge=1, le=200)):
    log_file = LOGS_DIR / "ailog.md"
    if not log_file.exists():
        return {"lines": [], "count": 0}

    lines = log_file.read_text(encoding="utf-8").splitlines()
    recent = lines[-limit:]
    return {"lines": recent, "count": len(recent)}


@app.post("/api/tasks")
async def submit_goal(request: GoalRequest):
    from core.ail_controller import AILController

    controller = AILController()
    result = controller.handle_goal(
        request.goal,
        repo=request.repo,
        constraints=request.constraints,
    )
    memory.rebuild()
    return result
