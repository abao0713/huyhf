"""
日志配置模块
提供统一的日志配置
"""

import logging
import sys
from pathlib import Path


def setup_logger(
    name: str = "trading_system",
    level: int = logging.INFO,
    log_file: str = None,
    format_string: str = None
) -> logging.Logger:
    """
    配置并返回logger实例
    
    Args:
        name: logger名称
        level: 日志级别
        log_file: 日志文件路径（可选）
        format_string: 自定义格式字符串（可选）
    
    Returns:
        配置好的Logger实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 默认格式
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    formatter = logging.Formatter(format_string)
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 文件输出（可选）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# 创建默认的logger实例
logger = setup_logger(
    name="trading_system",
    level=logging.INFO,
    log_file="trading_system.log"
)


if __name__ == "__main__":
    # 测试日志配置
    logger.debug("这是一条DEBUG级别的日志")
    logger.info("这是一条INFO级别的日志")
    logger.warning("这是一条WARNING级别的日志")
    logger.error("这是一条ERROR级别的日志")
    print("日志配置测试完成！")
