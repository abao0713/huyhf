import logging
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from trading_system.core.config import settings


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(settings.log_level_value)
    
    logger.handlers.clear()
    
    # 控制台日志处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level_value)
    
    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 创建logs目录
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
            print(f"Created logs directory: {log_dir}")
        except Exception as e:
            print(f"Error creating logs directory: {str(e)}")
    
    # 按日生成日志文件
    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, 'api_log'),
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(settings.log_level_value)
    file_handler.setFormatter(formatter)
    file_handler.suffix = '%Y-%m-%d.log'
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


logger = setup_logging()
