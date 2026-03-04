#!/usr/bin/env python3
"""
定时任务调度器

- 15:30 — Data 模块增量更新（POST /api/v1/data/sync）
- 16:00 — Quant 模块全策略信号生成
- 18:00 — Research 模块研报爬取
- 每周日 — 投资框架更新
- 每小时 — 数据库备份（scripts/backup.sh）

仅交易日执行数据相关任务。
"""

import logging
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------- 配置 ----------

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKUP_SCRIPT = Path(__file__).resolve().parent / "backup.sh"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


# ---------- 交易日判断 ----------

_trading_days_cache: set[str] | None = None


def is_trading_day(d: date | None = None) -> bool:
    """判断是否为交易日（周末直接返回False，工作日默认为交易日）"""
    if d is None:
        d = date.today()
    # 周末不是交易日
    if d.weekday() >= 5:
        return False
    # 尝试从 Data API 获取交易日历
    global _trading_days_cache
    if _trading_days_cache is None:
        try:
            resp = httpx.get(
                f"{BACKEND_URL}/api/v1/data/calendar",
                params={"year": d.year},
                timeout=10,
            )
            data = resp.json()
            if data.get("code") == 0 and data.get("data"):
                _trading_days_cache = {
                    item["date"]
                    for item in data["data"]
                    if item.get("is_trading_day")
                }
        except Exception:
            logger.debug("Cannot fetch trading calendar, assuming trading day")
            _trading_days_cache = set()

    if _trading_days_cache:
        return d.isoformat() in _trading_days_cache
    # 没有日历数据时，工作日默认为交易日
    return True


# ---------- 任务函数 ----------

def call_api(method: str, path: str, desc: str):
    """通用 API 调用"""
    url = f"{BACKEND_URL}{path}"
    logger.info(f"[{desc}] {method} {url}")
    try:
        if method == "POST":
            resp = httpx.post(url, timeout=300)
        else:
            resp = httpx.get(url, timeout=300)
        result = resp.json()
        logger.info(f"[{desc}] Response: code={result.get('code')}, message={result.get('message')}")
        return result
    except Exception as e:
        logger.error(f"[{desc}] Failed: {e}")
        return None


def job_data_sync():
    """15:30 — Data 模块增量更新"""
    if not is_trading_day():
        logger.info("[Data Sync] Not a trading day, skipping")
        return
    call_api("POST", "/api/v1/data/sync", "Data Sync")


def job_signal_generate():
    """16:00 — Quant 模块全策略信号生成"""
    if not is_trading_day():
        logger.info("[Signal Gen] Not a trading day, skipping")
        return
    # 触发所有已启用策略的信号生成
    call_api("POST", "/api/v1/signals/generate", "Signal Gen")


def job_research_crawl():
    """18:00 — Research 模块研报爬取"""
    if not is_trading_day():
        logger.info("[Research] Not a trading day, skipping")
        return
    call_api("POST", "/api/v1/research/crawl", "Research Crawl")


def job_framework_update():
    """每周日 — 投资框架更新"""
    call_api("POST", "/api/v1/research/framework/update", "Framework Update")


def job_backup():
    """每小时 — 数据库备份"""
    if not BACKUP_SCRIPT.exists():
        logger.warning(f"Backup script not found: {BACKUP_SCRIPT}")
        return
    logger.info("[Backup] Starting database backup")
    try:
        result = subprocess.run(
            ["bash", str(BACKUP_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            logger.info(f"[Backup] Success: {result.stdout.strip()}")
        else:
            logger.error(f"[Backup] Failed: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.error("[Backup] Timeout after 600s")
    except Exception as e:
        logger.error(f"[Backup] Error: {e}")


# ---------- 调度器 ----------

def create_scheduler() -> BlockingScheduler:
    """创建并配置调度器"""
    scheduler = BlockingScheduler()

    # 15:30 — 数据增量更新
    scheduler.add_job(
        job_data_sync,
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="data_sync",
        name="Data增量更新",
    )

    # 16:00 — 全策略信号生成
    scheduler.add_job(
        job_signal_generate,
        CronTrigger(hour=16, minute=0, day_of_week="mon-fri"),
        id="signal_generate",
        name="信号生成",
    )

    # 18:00 — 研报爬取
    scheduler.add_job(
        job_research_crawl,
        CronTrigger(hour=18, minute=0, day_of_week="mon-fri"),
        id="research_crawl",
        name="研报爬取",
    )

    # 每周日 — 投资框架更新
    scheduler.add_job(
        job_framework_update,
        CronTrigger(hour=10, minute=0, day_of_week="sun"),
        id="framework_update",
        name="投资框架更新",
    )

    # 每小时 — 数据库备份
    scheduler.add_job(
        job_backup,
        CronTrigger(minute=0),
        id="backup",
        name="数据库备份",
    )

    return scheduler


# ---------- 入口 ----------

def main():
    logger.info("Scheduler starting...")
    scheduler = create_scheduler()

    # 列出已注册的任务
    for job in scheduler.get_jobs():
        logger.info(f"  Job: {job.name} ({job.id}) -> {job.trigger}")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()
