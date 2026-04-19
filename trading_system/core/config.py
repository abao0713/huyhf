from pydantic_settings import BaseSettings
import logging


class Settings(BaseSettings):
    # 数据库连接配置
    database_url: str = "mysql+pymysql://root:305634841@localhost:3306/trading_db"
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = True
    
    # 日志配置
    log_level: str = "INFO"
    
    @property
    def log_level_value(self):
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        return level_map.get(self.log_level.upper(), logging.INFO)
    
    class Config:
        env_file = ".env"
        env_prefix = ""
        extra = "ignore"


settings = Settings()
