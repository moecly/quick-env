"""Logging utilities for quick-env."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_logger() -> logging.Logger:
    """Get or create the logger instance."""
    logger = logging.getLogger("quick_env")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_format = logging.Formatter("%(message)s")
        console_handler.setFormatter(console_format)

        logger.addHandler(console_handler)
    return logger


def _get_log_file_path() -> Path:
    """Get log file path with daily rotation."""
    from .config import get_env_paths

    paths = get_env_paths()
    log_dir = Path(paths["quick_env_logs"])
    log_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    return log_dir / f"quick-env-{today}.log"


def log_operation(
    operation: str,
    tool_name: str,
    method: str,
    level: str = "INFO",
    version: str = "",
    message: str = "",
):
    """通用的日志记录函数

    Args:
        operation: 操作类型 (INSTALL/UNINSTALL/UPGRADE/CHECK/LIST)
        tool_name: 工具名称
        method: 安装/操作方式 (github/custom_url/package_manager/dotfile/...)
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        version: 版本号 (可选)
        message: 附加消息 (可选)
    """
    logger = get_logger()
    log_file = _get_log_file_path()

    version_str = f" v{version}" if version else ""
    msg = f"[{operation}] {level} - {tool_name}{version_str}"
    if method:
        msg += f" via {method}"
    if message:
        msg += f" - {message}"

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"{timestamp} {msg}\n"

    if level == "ERROR":
        logger.error(msg)
    elif level == "WARNING":
        logger.warning(msg)
    elif level == "DEBUG":
        logger.debug(msg)
    else:
        logger.info(msg)

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass


def log_install(
    tool_name: str,
    method: str,
    level: str = "INFO",
    version: str = "",
    message: str = "",
):
    """记录安装操作 (兼容旧接口)"""
    log_operation("INSTALL", tool_name, method, level, version, message)


def log_uninstall(
    tool_name: str,
    level: str = "INFO",
    version: str = "",
    message: str = "",
):
    """记录卸载操作 (兼容旧接口)"""
    log_operation("UNINSTALL", tool_name, "", level, version, message)


def log_upgrade(
    tool_name: str,
    method: str,
    level: str = "INFO",
    version: str = "",
    message: str = "",
):
    """记录升级操作 (兼容旧接口)"""
    log_operation("UPGRADE", tool_name, method, level, version, message)


def log_check(
    tool_name: str,
    level: str = "INFO",
    message: str = "",
):
    """记录检查操作 (新增)"""
    log_operation("CHECK", tool_name, "", level, "", message)


def log_list(
    tool_name: str,
    level: str = "INFO",
    message: str = "",
):
    """记录列表操作 (新增)"""
    log_operation("LIST", tool_name, "", level, "", message)
