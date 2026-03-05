"""
Research模块CLI — 研报爬取、分析、框架生成、样本数据
用法：
    python -m backend.scripts.run_research crawl     # 爬取研报
    python -m backend.scripts.run_research analyze   # 分析未处理研报
    python -m backend.scripts.run_research framework # 生成投资框架
    python -m backend.scripts.run_research sample    # 生成样本数据
    python -m backend.scripts.run_research all       # 全流程
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def cmd_crawl():
    from backend.app.database import async_session
    from backend.app.services.research import crawl_eastmoney_reports
    async with async_session() as db:
        count = await crawl_eastmoney_reports(db)
        logger.info("爬取完成: %d 条新研报", count)


async def cmd_analyze():
    from backend.app.database import async_session
    from backend.app.services.research import analyze_pending_reports
    async with async_session() as db:
        count = await analyze_pending_reports(db)
        logger.info("分析完成: %d 条研报", count)


async def cmd_framework():
    from backend.app.database import async_session
    from backend.app.services.research import generate_frameworks
    async with async_session() as db:
        count = await generate_frameworks(db)
        logger.info("投资框架生成完成: %d 条", count)


async def cmd_sample():
    from backend.app.database import async_session
    from backend.app.services.sample_research_data import generate_sample_research
    async with async_session() as db:
        stats = await generate_sample_research(db)
        logger.info("样本数据: %s", stats)


async def cmd_all():
    logger.info("=== 开始全流程 ===")
    await cmd_sample()
    await cmd_crawl()
    await cmd_analyze()
    await cmd_framework()
    logger.info("=== 全流程完成 ===")


COMMANDS = {
    "crawl": cmd_crawl,
    "analyze": cmd_analyze,
    "framework": cmd_framework,
    "sample": cmd_sample,
    "all": cmd_all,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"用法: python -m backend.scripts.run_research <command>")
        print(f"可用命令: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    cmd = sys.argv[1]
    asyncio.run(COMMANDS[cmd]())


if __name__ == "__main__":
    main()
