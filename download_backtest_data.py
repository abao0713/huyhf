"""下载ETHUSDC回测所需的历史K线数据"""
import asyncio
import csv
from datetime import datetime, timedelta
from pathlib import Path
from binance.um_futures import UMFutures

DATA_DIR = Path(__file__).resolve().parent / "trading_system" / "data" / "binance_history"
SYMBOL = "ETHUSDC"
INTERVALS = ["4h", "30m", "15m", "1d"]
DAYS = 120  # 提前入场需要额外30天15m数据

BATCH_SIZE = 1000


async def download_interval(client: UMFutures, interval: str, start_ts: int, end_ts: int) -> list:
    all_data = []
    current_start = start_ts
    while True:
        print(f"  下载 {interval}: {datetime.fromtimestamp(current_start/1000)} ... (已获取 {len(all_data)} 条)")
        klines = client.klines(
            symbol=SYMBOL,
            interval=interval,
            startTime=current_start,
            endTime=end_ts,
            limit=BATCH_SIZE,
        )
        if not klines:
            break
        all_data.extend(klines)
        if len(klines) < BATCH_SIZE:
            break
        current_start = klines[-1][0] + 1
        await asyncio.sleep(0.2)
    return all_data


def save_to_csv(data: list, filename: str):
    filepath = DATA_DIR / filename
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades",
            "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        for row in data:
            writer.writerow([
                row[0], row[1], row[2], row[3], row[4], row[5],
                row[6], row[7], row[8], row[9], row[10], row[11]
            ])
    print(f"  已保存: {filepath} ({len(data)} 条)")


async def main():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS)
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    print(f"数据范围: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"数据目录: {DATA_DIR}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    client = UMFutures(base_url="https://testnet.binancefuture.com")
    client.session.trust_env = False

    for interval in INTERVALS:
        print(f"\n正在下载 {interval} K线...")
        try:
            data = await download_interval(client, interval, start_ts, end_ts)
            if data:
                save_to_csv(data, f"{SYMBOL}_{interval}.csv")
            else:
                print(f"  {interval}: 无数据返回")
        except Exception as e:
            print(f"  {interval}: 下载失败 - {e}")

    print("\n下载完成!")


if __name__ == "__main__":
    asyncio.run(main())