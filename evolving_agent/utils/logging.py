"""
Enhanced logging utilities for the self-improving agent.
"""

import os
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logger(name: str, log_level: Optional[str] = None) -> object:
    """
    Set up enhanced logging with loguru.

    Args:
        name: Logger name (usually __name__)
        log_level: Log level override

    Returns:
        Configured logger instance
    """
    # Remove default handler
    logger.remove()

    # Get log level from environment or use default
    level = log_level or os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "agent.log")

    # Console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>",
        level=level,
        colorize=True,
    )

    # File handler
    log_path = Path(log_file)
    log_path.parent.mkdir(exist_ok=True)

    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )

    return logger


# Configure the logger for this module using best practices
logger = setup_logger(__name__)

# Prevent log duplication if handlers are attached to the root logger
logger.propagate = False
