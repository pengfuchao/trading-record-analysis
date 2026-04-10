import logging
import os
from typing import Optional

_configured = False


def configure_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handlers = [logging.StreamHandler()]

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
