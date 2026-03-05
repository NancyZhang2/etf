"""
Pytest 配置 — 异步测试 + 数据库 fixture
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """测试用数据库引擎（会话级别，避免事件循环冲突）"""
    from backend.app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, pool_size=5)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(test_session_factory):
    """数据库会话"""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def api_client(test_engine):
    """FastAPI 测试客户端（使用独立数据库引擎）"""
    from httpx import ASGITransport, AsyncClient
    from backend.app.main import app
    from backend.app.database import get_db

    session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
