import gc
import logging
from contextlib import asynccontextmanager

from api_analytics.fastapi import Analytics
from fastapi import (
    FastAPI,
    Request,
)
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from . import db
from .env import env
from .log import LogMiddleware

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

print("\n")
logger.info("--------------- starting server ---------------")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.debug("calling init_db from lifespan")
    await db.init_db()
    yield
    # Shutdown
    gc.collect()


# Core Application Instance
app = FastAPI(
    title=env.PROJECT_NAME,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    # dependencies=[Depends(connection_report)],
)


# Thrown when reading invalid item from database (how did it get in there?)
@app.exception_handler(ResponseValidationError)
async def validation_error(request: Request, exc: ResponseValidationError):
    err = [str(e) for e in exc.errors()]
    return JSONResponse(
        status_code=418,
        content={
            "Database Validation Error": {
                "request": str(request.url.path),
                "detail": str(exc),
            },
            "body": str(exc.body[0]),
            "err": err,
            "err_type": f"{type(err[0])}",
            "errors_type": f"{type(exc.errors())}",
        },
    )


# Set all CORS origins enabled
if env.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in env.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Logging
app.add_middleware(LogMiddleware)

# Analytics https://www.apianalytics.dev/dashboard
app.add_middleware(Analytics, api_key=env.ANALYTICS_API_KEY)  # type: ignore

# Add Routers


@app.get("/ping")
async def ping():
    """
    An example "ping" FastAPI route. Useful to check server status.
    """
    return {"ping": "pong"}


# /ui
app.mount("/ui", StaticFiles(directory=env.UI_DIR, html=True), name="ui")


@app.get("/docs", include_in_schema=False)
async def api_documentation(request: Request):
    return HTMLResponse("""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>Elements in HTML</title>

    <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
  </head>
  <body>

    <elements-api
      apiDescriptionUrl="openapi.json"
      router="hash"
    />

  </body>
</html>""")
