Pull ETF data from tushare into PostgreSQL database.

## Usage

Run the tushare ETF data pull script. Supports three modes:

### Mode 1: Full Pull (ETF list + all history)
Pull the complete ETF list and all historical daily data. Skips ETFs that already have >100 records.

```bash
cd /data/etf/main && python3 -c "
import asyncio
from backend.app.database import async_session
from backend.app.services.tushare_data import sync_etf_list, pull_all_history

async def run():
    async with async_session() as db:
        print('=== 同步ETF列表 ===')
        r = await sync_etf_list(db)
        print(f'ETF列表: {r}')
        print()
        print('=== 拉取全量日线 ===')
        r = await pull_all_history(db, start_date='20100101')
        print(f'日线数据: {r}')

asyncio.run(run())
"
```

### Mode 2: Incremental Update (recent days only)
Pull data for the last N trading days. Fast, suitable for daily cron.

```bash
cd /data/etf/main && python3 -c "
import asyncio
from backend.app.database import async_session
from backend.app.services.tushare_data import incremental_update

async def run():
    async with async_session() as db:
        r = await incremental_update(db, days=5)
        print(f'增量更新: {r}')

asyncio.run(run())
"
```

### Mode 3: Single ETF
Pull history for a specific ETF by ts_code (e.g. 510300.SH).

```bash
cd /data/etf/main && python3 -c "
import asyncio
from backend.app.database import async_session
from backend.app.services.tushare_data import pull_daily_single

async def run():
    async with async_session() as db:
        r = await pull_daily_single(db, ts_code='$ARGUMENTS', start_date='20100101')
        print(f'新增记录: {r}')

asyncio.run(run())
"
```

## Notes
- tushare fund_daily 每次最多返回 2000 条，服务会自动分页
- 全量拉取 1400+ 只 ETF 耗时约 10-15 分钟
- 数据写入 etf_basic + etf_daily 表，ON CONFLICT 自动去重
- 服务文件：`backend/app/services/tushare_data.py`
