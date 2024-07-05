import logging
import logging.config


def setup_logger(
    name: str,
    log_file: str | None = None,
    level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """
    Sets up a logger with the specified name, log file, and log level.

    :param name: Name of the logger.
    :param log_file: Optional log file path. If provided, logs will be written to this file.
    :param level: Logging level. Default is logging.INFO.
    :param console: Boolean indicating if logs should be printed to console. Default is True.
    :return: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
