"""
Utility modules for the application.
"""

from app.utils.config import Config  # noqa
from app.utils.logger import setup_logger  # noqa
from app.utils.decorators import time_it  # noqa

try:
    from app.utils.storage import MultiThreadStorage, StorageManager  # noqa
    from app.utils.reader import FileReaderFactory, FileReaderStrategy  # noqa
    from app.utils.writer import FileWriterFactory, FileWriterStrategy  # noqa
except ImportError:
    pass

config = Config()

__all__ = [
    "Config",
    "config",
    "setup_logger",
    "time_it",
    "MultiThreadStorage",
    "StorageManager",
    "FileReaderFactory",
    "FileReaderStrategy",
    "FileWriterFactory",
    "FileWriterStrategy",
]
