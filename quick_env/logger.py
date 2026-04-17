"""Logging module for quick-env."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .platform import get_env_paths


_logger_cache: dict[str, logging.Logger] = {}


def _cleanup_old_logs(log_dir: Path, days: int = 7):
    """清理超过指定天数的日志"""
    cutoff = datetime.now() - timedelta(days=days)
    for log_file in log_dir.glob("*.log"):
        if log_file.stat().st_mtime < cutoff.timestamp():
            try:
                log_file.unlink()
            except OSError:
                pass


def get_logger(name: str = "quick-env") -> logging.Logger:
    """获取日志记录器（日志按天存储，保留 7 天）"""
    if name in _logger_cache:
        return _logger_cache[name]

    paths = get_env_paths()
    log_dir = Path(paths["quick_env_logs"])
    log_dir.mkdir(parents=True, exist_ok=True)

    _cleanup_old_logs(log_dir, days=7)

    log_file = log_dir / f"quick-env-{datetime.now():%Y%m%d}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.FileHandler(log_file, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    _logger_cache[name] = logger
    return logger


def log_install(tool_name: str, version: Optional[str], method: str, success: bool, message: str = ""):
    """记录安装操作"""
    logger = get_logger()
    status = "SUCCESS" if success else "FAILED"
    version_str = f" v{version}" if version else ""
    msg = f"[INSTALL] {status} - {tool_name}{version_str} via {method}"
    if message:
        msg += f" - {message}"
    if success:
        logger.info(msg)
    else:
        logger.error(msg)


def log_uninstall(tool_name: str, success: bool, message: str = ""):
    """记录卸载操作"""
    logger = get_logger()
    status = "SUCCESS" if success else "FAILED"
    msg = f"[UNINSTALL] {status} - {tool_name}"
    if message:
        msg += f" - {message}"
    if success:
        logger.info(msg)
    else:
        logger.error(msg)


def log_upgrade(tool_name: str, version: Optional[str], success: bool, message: str = ""):
    """记录升级操作"""
    logger = get_logger()
    status = "SUCCESS" if success else "FAILED"
    version_str = f" to v{version}" if version else ""
    msg = f"[UPGRADE] {status} - {tool_name}{version_str}"
    if message:
        msg += f" - {message}"
    if success:
        logger.info(msg)
    else:
        logger.error(msg)
