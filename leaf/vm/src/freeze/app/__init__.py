import json
import logging
import sys
import time
from os.path import isfile

import machine  # type: ignore

from eventbus.bus import Config, CurrentState, Log
from eventbus.event import set_src_addr

from .led import led, set_color  # noqa: F401

EPOCH_OFFSET = 946684800 if time.gmtime(0)[0] == 2000 else 0
CERT_DIR = "/certs"


# bail if branch is not yet provisioned
if not isfile("/secrets.json") or not isfile("/config.json"):
    from .led import RED

    set_color(RED)
    print("EXIT: no secrets.json or config.json")
    sys.exit(-1)


# logging must be configured before any actual logging
def configure_logging():
    class LogHandler(logging.Handler):
        def emit(self, record):
            from eventbus import eventbus
            from eventbus.event import log_event

            event = log_event(
                levelname=record.levelname,
                levelno=record.levelno,
                timestamp=record.ct + EPOCH_OFFSET,  # type: ignore
                name=record.name,
                message=record.message,
            )
            eventbus.emit_sync(event)
            # print("app.__init__ LOG", event)

    root_logger = logging.getLogger()
    # remove default handler
    root_logger.handlers = []
    root_logger.addHandler(LogHandler())


configure_logging()
logger = logging.getLogger(__name__)
Log()

# globals

mac = ":".join("{:02x}".format(x) for x in machine.unique_id())

with open("/secrets.json") as f:
    try:
        secrets = json.load(f)
    except ValueError:
        logger.error("Invalid secrets.json")
        sys.exit(-1)


tree_id = secrets.get("tree", {}).get("tree_id", "tree_id")
branch_id = "gateway"
for branch in secrets["tree"]["branches"]:
    if branch["mac"] == mac:
        branch_id = branch["branch_id"]
        break

set_src_addr(f"{tree_id}.{branch_id}")

# load config and current state
config = Config(config_file="/config.json")
state = CurrentState()

DOMAIN = config.get("domain")


# after loading config
from .main import main  # noqa: E402, F401
from .wifi import wifi  # noqa: E402, F401
