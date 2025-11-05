"""Logging configuration for Lab OCR application."""

import logging
import sys
from pathlib import Path
from typing import Optional

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_to_console: bool = True
) -> None:
    """
    Setup logging configuration for the application.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional log file path (default: logs/app.log)
        log_to_console: Whether to log to console (default: True)
    """
    if log_file is None:
        log_file = str(LOGS_DIR / 'app.log')
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(levelname)s - %(name)s - %(message)s'
    )
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

