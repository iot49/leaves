import json
import logging
import time
from logging import Formatter, Handler

from starlette.middleware.base import BaseHTTPMiddleware

"""
Log handler for Earth.

Forwards logging messages to eventbus.bus.log.
"""


class LogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        logger.info(
            "Incoming request",
            extra={
                "req": {"method": request.method, "url": str(request.url)},
                "res": {
                    "status_code": response.status_code,
                },
            },
        )
        return response


class JsonFormatter(Formatter):
    def __init__(self):
        super(JsonFormatter, self).__init__()

    def format(self, record):
        json_record = {}
        json_record["message"] = record.getMessage()
        if "req" in record.__dict__:
            json_record["req"] = record.__dict__["req"]
        if "res" in record.__dict__:
            json_record["res"] = record.__dict__["res"]
        if record.levelno == logging.ERROR and record.exc_info:
            json_record["err"] = self.formatException(record.exc_info)
        return json.dumps(json_record)


def print_log_message(event):
    BLUE = "\x1b[38;5;4m"
    GREEN = "\x1b[38;5;2m"
    YELLOW = "\x1b[38;5;3m"
    RED = "\x1b[38;5;1m"
    MAGENTA = "\x1b[38;5;5m"

    RESET = "\x1b[0m"
    levelno = event.get("levelno", 0)
    colors = {
        logging.DEBUG: BLUE,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: MAGENTA,
    }
    color = colors.get(levelno, "")
    funcName = event.get("funcName") or ""
    t = time.strftime(
        "app/log.py %Y-%m-%d %H:%M:%S", time.gmtime(event.get("timestamp", 0))
    )  # type: ignore
    print(
        f"{t} {color}{event.get('levelname'):9}{RESET} {event.get('src'):12} {event.get('name'):20} {funcName:16} {event.get('message')}"
    )
    tb = event.get("traceback")
    if tb is not None:
        print(tb)


class EventLogHandler(Handler):
    def __init__(self):
        super(EventLogHandler, self).__init__()

    def emit(self, record):
        pass


logger = logging.root
logger.handlers = [EventLogHandler()]
logger.setLevel(logging.ERROR)

logging.getLogger("uvicorn.access").disabled = True

# handler.setFormatter(JsonFormatter())
