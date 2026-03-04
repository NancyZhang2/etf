#!/usr/bin/env python3
"""
Web Manager — 手机友好的管理界面（端口8080）

功能：
- 任务看板（5个模块，待开始/进行中/已完成）
- Worker 运行状态
- 日志查看
- 任务派发
- WebSocket 实时日志推送
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# ---------- 路径常量 ----------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = PROJECT_ROOT / "modules"
LOGS_DIR = PROJECT_ROOT / "logs"

MODULE_NAMES = ["data", "quant", "research", "frontend", "notification"]

# ---------- App ----------

app = FastAPI(title="ETF Web Manager", version="0.1.0")

# 静态文件
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------- TODO.md 解析 ----------

def parse_todo_md(module: str) -> list[dict]:
    """解析模块的 TODO.md"""
    todo_path = MODULES_DIR / module / "TODO.md"
    if not todo_path.exists():
        return []

    content = todo_path.read_text(encoding="utf-8")
    tasks = []
    current = None

    for line in content.split("\n"):
        header_match = re.match(r"^## ([A-Z]\d+)\.\s+(.+)$", line.strip())
        if header_match:
            if current:
                tasks.append(current)
            current = {
                "id": header_match.group(1),
                "title": header_match.group(2),
                "status": "",
                "priority": "",
                "module": module,
            }
            continue

        if current is None:
            continue

        status_match = re.match(r"^状态：(.+)$", line.strip())
        if status_match:
            current["status"] = status_match.group(1).strip()

        priority_match = re.match(r"^优先级：(.+)$", line.strip())
        if priority_match:
            current["priority"] = priority_match.group(1).strip()

    if current:
        tasks.append(current)

    return tasks


# ---------- API 路由 ----------

@app.get("/", response_class=HTMLResponse)
async def index():
    """管理首页"""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>ETF Web Manager</h1><p>static/index.html not found</p>")


@app.get("/api/tasks")
async def get_tasks():
    """获取所有模块任务状态"""
    result = {}
    for module in MODULE_NAMES:
        result[module] = parse_todo_md(module)
    return {"code": 0, "data": result, "message": "ok"}


@app.post("/api/tasks/dispatch")
async def dispatch_task(module: str, task_id: str):
    """派发任务：将任务标记为待开始（供 Orchestrator 发现）"""
    todo_path = MODULES_DIR / module / "TODO.md"
    if not todo_path.exists():
        return {"code": 404, "data": None, "message": f"Module {module} not found"}

    content = todo_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    in_task = False
    updated = False

    for i, line in enumerate(lines):
        header_match = re.match(r"^## ([A-Z]\d+)\.\s+", line.strip())
        if header_match:
            in_task = header_match.group(1) == task_id
            continue
        if in_task and re.match(r"^状态：", line.strip()):
            lines[i] = "状态：待开始"
            updated = True
            break

    if updated:
        todo_path.write_text("\n".join(lines), encoding="utf-8")
        return {"code": 0, "data": {"module": module, "task_id": task_id}, "message": "ok"}
    return {"code": 404, "data": None, "message": f"Task {task_id} not found"}


@app.get("/api/workers")
async def get_workers():
    """获取 Worker 运行状态（扫描日志目录）"""
    workers = []
    if LOGS_DIR.exists():
        for log_file in sorted(LOGS_DIR.glob("*.jsonl"), reverse=True)[:20]:
            name = log_file.stem
            parts = name.split("-")
            module = parts[0] if parts else "unknown"
            stat = log_file.stat()
            workers.append({
                "file": log_file.name,
                "module": module,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return {"code": 0, "data": workers, "message": "ok"}


@app.get("/api/logs/{module}")
async def get_logs(module: str, lines: int = 100):
    """查看模块最新日志"""
    if not LOGS_DIR.exists():
        return {"code": 0, "data": [], "message": "ok"}

    log_files = sorted(LOGS_DIR.glob(f"{module}-*.jsonl"), reverse=True)
    if not log_files:
        return {"code": 0, "data": [], "message": "No logs found"}

    latest = log_files[0]
    log_lines = []
    try:
        with open(latest, "r") as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                line = line.strip()
                if line:
                    try:
                        log_lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        log_lines.append({"raw": line})
    except Exception as e:
        return {"code": 500, "data": None, "message": str(e)}

    return {"code": 0, "data": {"file": latest.name, "lines": log_lines}, "message": "ok"}


# ---------- WebSocket 实时日志 ----------

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        self.connections.remove(ws)

    async def broadcast(self, message: str):
        for ws in self.connections:
            try:
                await ws.send_text(message)
            except Exception:
                pass


manager = ConnectionManager()


@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket 实时日志推送"""
    await manager.connect(websocket)
    try:
        while True:
            # 等待客户端消息（保持连接活跃）
            data = await websocket.receive_text()
            # 客户端可发送模块名来过滤日志
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------- 入口 ----------

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEB_MANAGER_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
