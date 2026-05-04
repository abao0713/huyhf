import os
import logging
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


class BacktestDataManager:
    """回测数据管理器 - 负责加载本地CSV数据文件"""

    def __init__(self, data_dir: str):
        """
        初始化数据管理器

        Args:
            data_dir: 数据文件目录路径
        """
        self.data_dir = data_dir
        logger.info(f"[BacktestDataManager] 初始化，数据目录: {data_dir}")

    def load_klines_from_csv(self, filename: str) -> pd.DataFrame:
        """
        从CSV文件加载K线数据

        Args:
            filename: CSV文件名（如 "ETHUSDT_30m.csv"）

        Returns:
            包含K线数据的DataFrame，加载失败返回空DataFrame
        """
        file_path = os.path.join(self.data_dir, filename)

        if not os.path.exists(file_path):
            logger.error(f"[BacktestDataManager] 文件不存在: {file_path}")
            return pd.DataFrame()

        try:
            df = pd.read_csv(file_path)
            logger.info(f"[BacktestDataManager] 成功加载: {filename} ({len(df)} 条记录)")
            return df

        except Exception as e:
            logger.error(f"[BacktestDataReader] 读取文件失败 {filename}: {e}")
            return pd.DataFrame()

    def download_and_save_data(
        self,
        symbol: str,
        intervals: list,
        start_time: str,
        end_time: str
    ) -> dict:
        """
        下载并保存K线数据（兼容旧接口）

        Args:
            symbol: 交易对（如 "ETHUSDT"）
            intervals: K线周期列表（如 ["30m", "1d"]）
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            保存的文件字典 {interval: file_path}
        """
        import asyncio
        from trading_system.okx.client import BinanceRestClient
        from datetime import datetime

        saved_files = {}

        async def _download():
            client = BinanceRestClient()
            try:
                start_ts = int(datetime.strptime(start_time, "%Y-%m-%d").timestamp() * 1000)
                end_ts = int(datetime.strptime(end_time, "%Y-%m-%d").timestamp() * 1000)

                for interval in intervals:
                    all_data = []
                    current_start = start_ts
                    batch_num = 0
                    BATCH_SIZE = 1000

                    while True:
                        data = await client.get_spot_klines(
                            symbol=symbol,
                            interval=interval,
                            startTime=current_start,
                            endTime=end_ts,
                            limit=BATCH_SIZE
                        )

                        if not data or (isinstance(data, dict) and "error" in data):
                            break

                        all_data.extend(data)
                        batch_num += 1

                        received = len(data) if isinstance(data, list) else 0

                        if received < BATCH_SIZE:
                            break

                        last_timestamp = data[-1][0]
                        current_start = last_timestamp + 1
                        await asyncio.sleep(0.2)

                    if all_data:
                        df = pd.DataFrame(all_data, columns=[
                            "open_time", "open", "high", "low", "close", "volume",
                            "close_time", "quote_volume", "trades", "taker_buy_base",
                            "taker_buy_quote", "ignore"
                        ])

                        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
                        df = df.drop_duplicates(subset=["open_time"])
                        df = df.sort_values("open_time").reset_index(drop=True)

                        for col in ["open", "high", "low", "close", "volume"]:
                            df[col] = pd.to_numeric(df[col], errors='coerce')

                        df = df[["open_time", "open", "high", "low", "close", "volume"]]

                        save_filename = f"{symbol}_{interval}.csv"
                        save_path = os.path.join(self.data_dir, save_filename)
                        os.makedirs(self.data_dir, exist_ok=True)
                        df.to_csv(save_path, index=False)

                        saved_files[interval] = save_path
                        logger.info(f"[BacktestDataManager] 已保存 {interval} 数据: {save_path} ({len(df)}条)")

            finally:
                await client.close()

        asyncio.run(_download())
        return saved_files
