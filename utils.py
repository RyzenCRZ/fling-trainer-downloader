"""通用工具模块 — 日志、重试装饰器、格式化函数"""
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# 日志目录
APP_DIR = Path.home() / ".fling_trainer"
LOG_DIR = APP_DIR / "logs"

# 全局日志实例
_logger: logging.Logger | None = None


def setup_logger() -> logging.Logger:
    """配置日志器，按天滚动日志文件"""
    global _logger
    if _logger is not None:
        return _logger

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "app.log"

    _logger = logging.getLogger("fling_trainer")
    _logger.setLevel(logging.DEBUG)

    # 按天滚动，保留 30 天
    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )

    # 控制台输出（打包后无效，开发时用）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(message)s")
    )

    _logger.addHandler(file_handler)
    _logger.addHandler(console_handler)
    return _logger


def get_logger() -> logging.Logger:
    """获取日志器（已初始化则直接返回）"""
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def retry(times=3, delay=1.0):
    """重试装饰器，用于网络操作"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exc = None
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    get_logger().warning(f"第 {i+1}/{times} 次尝试失败: {e}")
                    if i < times - 1:
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_idx = 0
    size = float(size_bytes)
    while size >= 1024 and unit_idx < len(units) - 1:
        size /= 1024
        unit_idx += 1
    return f"{size:.1f} {units[unit_idx]}"


def format_speed(bytes_per_sec: float) -> str:
    """格式化下载速度"""
    return f"{format_size(int(bytes_per_sec))}/s"


def format_time(seconds: float) -> str:
    """格式化剩余时间"""
    if seconds <= 0 or seconds == float("inf"):
        return "--"
    if seconds < 60:
        return f"{int(seconds)}秒"
    if seconds < 3600:
        return f"{int(seconds / 60)}分{int(seconds % 60)}秒"
    return f"{int(seconds / 3600)}时{int((seconds % 3600) / 60)}分"
