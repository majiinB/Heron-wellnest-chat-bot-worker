import logging
import os
from typing import Optional
from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler

class LoggerUtil:
    """
    Logger utility for the NLP Worker API.

    This module sets up a Python logger with different handlers based on the environment.
    In production, it uses Google Cloud Logging; in development, it logs to the console.
    """

    def __init__(self):
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """
        Configure and return a logger instance based on environment.

        Returns:
            logging.Logger: Configured logger instance
        """
        # Get environment
        env_mode = os.getenv("ENVIRONMENT", "development")

        # Create logger
        logger = logging.getLogger("nlp_worker")
        logger.setLevel(logging.INFO)

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()

        # Console handler for all environments
        console_handler = logging.StreamHandler()

        if env_mode == "production":
            # Production: JSON format + Google Cloud Logging
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(name)s"}'
            )
            console_handler.setFormatter(formatter)

            # Add Google Cloud Logging handler for production
            try:
                client = cloud_logging.Client()
                cloud_handler = CloudLoggingHandler(client)
                logger.addHandler(cloud_handler)
            except Exception as e:
                logger.warning(f"Failed to initialize Google Cloud Logging: {e}")
        else:
            # Development: Colorized simple format
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        return logger

    def info(self, message: str, *args, **kwargs):
        self.logger.info(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self.logger.error(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs):
        self.logger.debug(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self.logger.exception(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self.logger.critical(message, *args, **kwargs)

# Create singleton logger instance
logger = LoggerUtil()