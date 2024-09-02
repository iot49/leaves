# ruff: noqa: F821
# type: ignore

# default imports
include("$(BOARD_DIR)/manifest.py")

module("version.py")
module("main.py")
freeze("lib")

# packages
package("app")
package("plugins")
# package("eventbus", base_path="/project/eventbus")
package("eventbus", base_path="../../../../eventbus")

# micropython-lib
require("aioble")
require("bmi270")
require("espflash")

# require("aiohttp")  bug in ws
require("iperf3")
require("pyjwt")

require("abc")
require("base64")
require("bisect")
require("collections")
require("contextlib")
require("copy")
require("curses.ascii")
require("datetime")
require("fnmatch")
require("functools")
require("gzip")
require("hashlib")
require("hmac")
require("html")
require("inspect")
require("io")
require("itertools")
require("keyword")
require("locale")
require("logging")
require("operator")
require("os-path")
require("os")
require("pathlib")
require("shutil")
require("stat")
require("string")
require("textwrap")
require("time")
require("traceback")
# require("unittest-discover")
# require("urllib.urequest")  no redirects
require("uu")
require("zlib")
