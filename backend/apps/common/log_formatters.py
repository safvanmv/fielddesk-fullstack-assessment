import json
import logging
from datetime import datetime, timezone

from .middleware import request_id_context


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_context.get()
        if request_id:
            entry["request_id"] = request_id
        for field in ("request_id", "work_order_id", "outcome", "attempts", "notification_key", "technician"):
            value = getattr(record, field, None)
            if field != "request_id" and value is not None:
                entry[field] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, separators=(",", ":"))
