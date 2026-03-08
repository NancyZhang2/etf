"""
为所有活跃策略创建虚拟账户（幂等，已有则跳过）。
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    from backend.app.database import async_session
    from backend.app.models.strategy import Strategy
    from backend.app.services.virtual_portfolio import create_account, get_account
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(Strategy).where(Strategy.is_active == True))
        strategies = result.scalars().all()
        logger.info("共 %d 个活跃策略", len(strategies))

        created = 0
        for s in strategies:
            existing = await get_account(db, s.id)
            if existing:
                logger.info("跳过: %s (id=%d) 已有虚拟账户", s.name, s.id)
                continue
            account = await create_account(db, s.id)
            created += 1
            logger.info("已创建: %s (id=%d), account_id=%d, 初始资金=200000",
                        s.name, s.id, account.id)

        await db.commit()
        logger.info("完成: 共创建 %d 个虚拟账户", created)


if __name__ == "__main__":
    asyncio.run(main())
