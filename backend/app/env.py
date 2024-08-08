import os
from datetime import timedelta
from enum import Enum
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import AnyHttpUrl, EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    prod = "prod"
    dev = "dev"
    test = "test"


class Env(BaseSettings):
    """Loads the dotenv file. Including this is necessary to get
    pydantic to load a .env file."""

    ENVIRONMENT: Environment = Environment.prod

    PROJECT_NAME: str = "leaf"
    DOMAIN: str = "leaf49.org"

    FIRST_SUPERUSER_EMAIL: EmailStr

    # database
    POSTGRES_USERNAME: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    DATABASE_ECHO: bool = False

    CONFIG_DIR: str = "/home/config"

    # cloudflare tunnel
    CF_POLICY_AUD: str
    CF_TEAM_DOMAIN: str = "https://leaf49.cloudflareaccess.com"

    # api keys (beware of slow networks)
    API_KEY_VALIDITY: timedelta = timedelta(days=100 * 365)
    CLIENT_EARTH_VALIDITY: timedelta = timedelta(minutes=5)
    CLIENT_GATEWAY_VALIDITY: timedelta = timedelta(days=30)
    GATEWAY_EARTH_VALIDITY: timedelta = timedelta(days=90)

    # websocket timeouts
    CLIENT_WS_TIMEOUT: int = 10  # server disconnects if no message received (seconds)
    GATEWAY_WS_TIMEOUT: int = 10  # server disconnects if no message received (seconds)

    # analytics https://www.apianalytics.dev/dashboard
    ANALYTICS_API_KEY: str | None = None

    # github repo
    GITHUB_OWNER: str = "iot49"
    GITHUB_REPO: str = "leaf"

    model_config = SettingsConfigDict(
        # env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def DATABASE_URL(self) -> str:
        if self.ENVIRONMENT == Environment.prod:
            # return f"postgresql+asyncpg://{self.POSTGRES_USERNAME}:{self.POSTGRES_PASSWORD}@database:5432/{self.PROJECT_NAME}_{self.ENVIRONMENT.value}"
            return f"sqlite+aiosqlite:///sqlite-{self.PROJECT_NAME}-{self.ENVIRONMENT.value}.db"
        if self.ENVIRONMENT == Environment.dev:
            # return f"postgresql+asyncpg://{self.POSTGRES_USERNAME}:{self.POSTGRES_PASSWORD}@192.168.8.191:5432/{self.PROJECT_NAME}_{self.ENVIRONMENT.value}"
            return f"sqlite+aiosqlite:///sqlite-{self.PROJECT_NAME}-{self.ENVIRONMENT.value}.db"
        # in memory database raises sqlalchemy.exc.InvalidRequestError: Could not refresh instance (on session.refresh(obj))
        # https://blog.osull.com/2022/06/27/async-in-memory-sqlite-sqlalchemy-database-for-fastapi/
        return "sqlite+aiosqlite:///"
        # return "sqlite+aiosqlite:///sqlite-test.db"

    @property
    def BACKEND_CORS_ORIGINS(self) -> list[str] | list[AnyHttpUrl]:
        if self.ENVIRONMENT == Environment.dev:
            return ["http://localhost:5173", "http://localhost:4173"]
        return []

    @property
    def UI_DIR(self) -> str:
        dir = "/home/ui"
        return dir if os.path.isdir(dir) else "../../ui/dist"


@lru_cache()
def get_env():
    load_dotenv()
    return Env()  # type: ignore


env = get_env()
