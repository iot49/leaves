# ruff:  noqa: F401

import sys
import time

from .with_cd import WithCD


def ticks_ms():
    try:
        return time.ticks_ms()  # type: ignore
    except AttributeError:
        return int(time.time() * 1000)


def is_micropython():
    return "micropython" in sys.implementation.name
