# type: ignore

import sys

if "." not in sys.path:
    sys.path.append(".")

import machine
from app.led import BLUE, RED, set_color

# note: print output appears no-where - write to file?

RESET_CAUSE = {
    machine.PWRON_RESET: "power-on",
    machine.HARD_RESET: "hard reset",
    machine.WDT_RESET: "watchdog timer",
    machine.DEEPSLEEP_RESET: "deepsleep reset",
    machine.SOFT_RESET: "soft reset",
}

print("reset-cause:", RESET_CAUSE.get(machine.reset_cause(), machine.reset_cause()))

set_color(RED)  # normal startup

if machine.reset_cause == machine.SOFT_RESET:
    print("soft reset - exiting to REPL")
else:
    try:
        open("/main.py")  # OSError if file does not exist
        print("starting from /main.py")
        set_color(BLUE)  # main override
        __import__("main")  # import /main.py
    except Exception:
        import asyncio

        from app import main

        print("starting from frozen main.py")
        asyncio.new_event_loop()
        asyncio.run(main())

    print("exiting to REPL")
