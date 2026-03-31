import logging
import os
from typing import List

logger = logging.getLogger(__name__)


class Config:
    """Configuration loaded and validated from environment variables."""

    _ALLOWED_LOG_LEVELS: List[str] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def __init__(self, bedrock_model_id: str, log_level: str) -> None:
        self.bedrock_model_id = bedrock_model_id
        self.log_level = log_level

    @classmethod
    def from_env(cls) -> "Config":
        """Load and validate configuration from environment variables.

        Raises:
            ValueError: If required environment variables are missing or invalid.
        """
        bedrock_model_id: str = os.environ.get(
            "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
        )

        log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
        if log_level not in cls._ALLOWED_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {cls._ALLOWED_LOG_LEVELS}")

        return cls(
            bedrock_model_id=bedrock_model_id,
            log_level=log_level,
        )
