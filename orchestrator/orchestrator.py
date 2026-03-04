#!/usr/bin/env python3
"""
Orchestrator — 核心调度器

监控5个模块的 TODO.md，发现未完成任务时启动 Worker（Claude Code 实例）。
支持最多5个 Worker 并行，每个模块最多1个。
解析 Worker 的 stream-json 日志，失败时带诊断信息重试（最多2次）。

用法：
    python orchestrator/orchestrator.py              # 正常运行
    python orchestrator/orchestrator.py --dry-run     # 仅解析任务，不启动 Worker
    python orchestrator/orchestrator.py --once        # 执行一轮后退出
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------- 路径常量 ----------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = PROJECT_ROOT / "modules"
LOGS_DIR = PROJECT_ROOT / "logs"
PROMPT_TEMPLATE = Path(__file__).resolve().parent / "worker_prompt_template.txt"

MODULE_NAMES = ["data", "quant", "research", "frontend", "notification"]

MAX_TOTAL_WORKERS = 5
MAX_RETRIES = 2
POLL_INTERVAL = 30  # 秒

# ---------- 日志 ----------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orchestrator")


# ---------- 数据结构 ----------

@dataclass
class Task:
    """从 TODO.md 解析出的任务"""
    task_id: str          # 例如 "D1"
    title: str            # 任务标题
    status: str           # 待开始 / 进行中 / 已完成 / BLOCKED
    priority: str = ""    # P0 / P1 / P2
    depends: list = field(default_factory=list)
    description: str = ""
    module: str = ""


@dataclass
class WorkerState:
    """Worker 运行状态"""
    module: str
    task: Task
    process: Optional[subprocess.Popen] = None
    log_path: Optional[Path] = None
    start_time: Optional[datetime] = None
    retry_count: int = 0


# ---------- TODO.md 解析 ----------

def parse_todo_md(module: str) -> list[Task]:
    """解析模块的 TODO.md，提取任务列表"""
    todo_path = MODULES_DIR / module / "TODO.md"
    if not todo_path.exists():
        logger.warning(f"TODO.md not found: {todo_path}")
        return []

    content = todo_path.read_text(encoding="utf-8")
    tasks = []
    current_task = None

    for line in content.split("\n"):
        # 匹配任务标题：## D1. PostgreSQL 建库建表
        header_match = re.match(r"^## ([A-Z]\d+)\.\s+(.+)$", line.strip())
        if header_match:
            if current_task:
                tasks.append(current_task)
            current_task = Task(
                task_id=header_match.group(1),
                title=header_match.group(2),
                status="",
                module=module,
            )
            continue

        if current_task is None:
            continue

        # 匹配状态
        status_match = re.match(r"^状态：(.+)$", line.strip())
        if status_match:
            current_task.status = status_match.group(1).strip()
            continue

        # 匹配优先级
        priority_match = re.match(r"^优先级：(.+)$", line.strip())
        if priority_match:
            current_task.priority = priority_match.group(1).strip()
            continue

        # 匹配依赖
        dep_match = re.match(r"^依赖：(.+)$", line.strip())
        if dep_match:
            current_task.depends = [
                d.strip() for d in dep_match.group(1).split(",")
            ]
            continue

        # 匹配描述
        desc_match = re.match(r"^描述：(.+)$", line.strip())
        if desc_match:
            current_task.description = desc_match.group(1).strip()
            continue

    if current_task:
        tasks.append(current_task)

    return tasks


def get_pending_tasks(module: str) -> list[Task]:
    """获取模块中所有待开始的任务（按优先级排序）"""
    tasks = parse_todo_md(module)
    completed_ids = {t.task_id for t in tasks if t.status == "已完成"}

    pending = []
    for t in tasks:
        if t.status != "待开始":
            continue
        # 检查依赖是否全部完成
        unmet = [d for d in t.depends if d not in completed_ids]
        if unmet:
            logger.debug(
                f"[{module}] {t.task_id} blocked by: {unmet}"
            )
            continue
        pending.append(t)

    # P0 优先
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    pending.sort(key=lambda t: priority_order.get(t.priority, 9))
    return pending


# ---------- TODO.md 状态更新 ----------

def update_task_status(module: str, task_id: str, new_status: str):
    """更新 TODO.md 中某任务的状态"""
    todo_path = MODULES_DIR / module / "TODO.md"
    content = todo_path.read_text(encoding="utf-8")

    # 找到任务段落，替换状态行
    lines = content.split("\n")
    in_task = False
    for i, line in enumerate(lines):
        header_match = re.match(r"^## ([A-Z]\d+)\.\s+", line.strip())
        if header_match:
            in_task = header_match.group(1) == task_id
            continue
        if in_task and re.match(r"^状态：", line.strip()):
            lines[i] = f"状态：{new_status}"
            break

    todo_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[{module}] {task_id} status -> {new_status}")


# ---------- Worker 管理 ----------

def build_worker_prompt(task: Task) -> str:
    """根据任务和模板生成 Worker prompt"""
    if PROMPT_TEMPLATE.exists():
        template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    else:
        template = "请完成以下任务：\n{task_description}"

    return template.format(
        module=task.module,
        task_id=task.task_id,
        task_title=task.title,
        task_description=task.description,
        task_priority=task.priority,
    )


def start_worker(task: Task, retry_info: str = "") -> WorkerState:
    """启动一个 Worker 进程"""
    prompt = build_worker_prompt(task)
    if retry_info:
        prompt += f"\n\n--- 上次失败诊断 ---\n{retry_info}"

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOGS_DIR / f"{task.module}-{task.task_id}-{timestamp}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    worktree_dir = PROJECT_ROOT.parent / f"worktree-{task.module}"
    work_dir = worktree_dir if worktree_dir.exists() else PROJECT_ROOT

    cmd = [
        "claude",
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--verbose",
    ]

    logger.info(
        f"[{task.module}] Starting worker for {task.task_id}: {task.title}"
    )
    logger.info(f"[{task.module}] Work dir: {work_dir}")
    logger.info(f"[{task.module}] Log: {log_path}")

    log_file = open(log_path, "w")
    process = subprocess.Popen(
        cmd,
        cwd=work_dir,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    state = WorkerState(
        module=task.module,
        task=task,
        process=process,
        log_path=log_path,
        start_time=datetime.now(),
    )
    return state


def diagnose_failure(log_path: Path) -> str:
    """解析 Worker 日志，提取失败诊断信息"""
    if not log_path or not log_path.exists():
        return "日志文件不存在"

    errors = []
    try:
        with open(log_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    # 提取错误相关事件
                    if event.get("type") == "error":
                        errors.append(event.get("message", ""))
                    elif "error" in str(event).lower():
                        errors.append(json.dumps(event, ensure_ascii=False)[:500])
                except json.JSONDecodeError:
                    if "error" in line.lower() or "traceback" in line.lower():
                        errors.append(line[:500])
    except Exception as e:
        return f"日志解析失败: {e}"

    if errors:
        return "\n".join(errors[-5:])  # 最后5条错误
    return "Worker 退出但未发现明确错误信息"


# ---------- 主循环 ----------

class Orchestrator:
    """调度器主类"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.active_workers: dict[str, WorkerState] = {}  # module -> WorkerState
        self.retry_counts: dict[str, int] = {}  # "module:task_id" -> count

    def scan_all_modules(self) -> dict[str, list[Task]]:
        """扫描所有模块的待办任务"""
        result = {}
        for module in MODULE_NAMES:
            tasks = get_pending_tasks(module)
            if tasks:
                result[module] = tasks
        return result

    def check_workers(self):
        """检查活跃 Worker 状态，处理完成/失败"""
        finished = []
        for module, worker in self.active_workers.items():
            if worker.process.poll() is not None:
                finished.append(module)
                return_code = worker.process.returncode
                task = worker.task
                key = f"{module}:{task.task_id}"

                if return_code == 0:
                    logger.info(
                        f"[{module}] Worker completed: {task.task_id}"
                    )
                    update_task_status(module, task.task_id, "已完成")
                    self.retry_counts.pop(key, None)
                else:
                    count = self.retry_counts.get(key, 0)
                    diagnosis = diagnose_failure(worker.log_path)
                    logger.warning(
                        f"[{module}] Worker failed (exit={return_code}): "
                        f"{task.task_id}, retry {count}/{MAX_RETRIES}"
                    )
                    logger.warning(f"[{module}] Diagnosis: {diagnosis}")

                    if count < MAX_RETRIES:
                        self.retry_counts[key] = count + 1
                        update_task_status(module, task.task_id, "待开始")
                        # 下一轮循环会自动重试
                    else:
                        logger.error(
                            f"[{module}] {task.task_id} BLOCKED after "
                            f"{MAX_RETRIES} retries"
                        )
                        update_task_status(module, task.task_id, "BLOCKED")
                        self.retry_counts.pop(key, None)

        for module in finished:
            del self.active_workers[module]

    def dispatch_workers(self, pending: dict[str, list[Task]]):
        """根据限制条件调度新 Worker"""
        for module, tasks in pending.items():
            # 每模块最多1个 Worker
            if module in self.active_workers:
                continue
            # 总 Worker 数限制
            if len(self.active_workers) >= MAX_TOTAL_WORKERS:
                break

            task = tasks[0]  # 取最高优先级的一个
            key = f"{module}:{task.task_id}"
            retry_count = self.retry_counts.get(key, 0)

            retry_info = ""
            if retry_count > 0:
                # 查找上次的日志
                prev_workers = sorted(
                    LOGS_DIR.glob(f"{module}-{task.task_id}-*.jsonl")
                )
                if prev_workers:
                    retry_info = diagnose_failure(prev_workers[-1])

            if self.dry_run:
                logger.info(
                    f"[DRY-RUN] Would start worker: "
                    f"{module}/{task.task_id} - {task.title}"
                )
                continue

            update_task_status(module, task.task_id, "进行中")
            worker = start_worker(task, retry_info)
            worker.retry_count = retry_count
            self.active_workers[module] = worker

    def run_once(self):
        """执行一轮：检查 + 扫描 + 调度"""
        self.check_workers()
        pending = self.scan_all_modules()

        if pending:
            logger.info(
                f"Pending tasks: "
                + ", ".join(
                    f"{m}({len(t)})" for m, t in pending.items()
                )
            )
            self.dispatch_workers(pending)
        else:
            if not self.active_workers:
                logger.info("No pending tasks and no active workers")

        if self.active_workers:
            logger.info(
                f"Active workers: "
                + ", ".join(
                    f"{m}:{w.task.task_id}"
                    for m, w in self.active_workers.items()
                )
            )

    def run(self, once: bool = False):
        """主循环"""
        logger.info("Orchestrator started")
        if self.dry_run:
            logger.info("DRY-RUN mode: will not start workers")

        try:
            while True:
                self.run_once()
                if once or self.dry_run:
                    break
                time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Orchestrator interrupted, stopping workers...")
            for module, worker in self.active_workers.items():
                if worker.process.poll() is None:
                    worker.process.terminate()
                    logger.info(f"[{module}] Worker terminated")
            logger.info("Orchestrator stopped")


# ---------- 入口 ----------

def main():
    parser = argparse.ArgumentParser(description="ETF Orchestrator")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅解析任务，不启动 Worker",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="执行一轮后退出",
    )
    args = parser.parse_args()

    orchestrator = Orchestrator(dry_run=args.dry_run)
    orchestrator.run(once=args.once)


if __name__ == "__main__":
    main()
