import sys
sys.path.append(".")

import asyncio

from app import app_main

asyncio.run(app_main())
