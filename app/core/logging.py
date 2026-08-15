import json
import logging

from app.config import get_settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    
    # Enable file logging for administrative log viewer
    file_handler = logging.FileHandler("app.log", encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    
    logging.basicConfig(level=settings.log_level, handlers=[handler, file_handler], force=True)
