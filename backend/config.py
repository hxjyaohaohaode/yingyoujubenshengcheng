import os
from dotenv import load_dotenv

load_dotenv()

_raw_database_url = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./script_engine.db"
)

if _raw_database_url.startswith("postgresql://"):
    DATABASE_URL = _raw_database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = _raw_database_url

DATABASE_URL_SYNC = os.getenv("DATABASE_URL_SYNC", "")
if not DATABASE_URL_SYNC:
    if DATABASE_URL.startswith("postgresql+asyncpg://"):
        DATABASE_URL_SYNC = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif DATABASE_URL.startswith("sqlite+aiosqlite:///"):
        DATABASE_URL_SYNC = DATABASE_URL.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    else:
        DATABASE_URL_SYNC = DATABASE_URL

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

GIT_REPO_PATH = os.getenv("GIT_REPO_PATH", "./data/repos")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000").split(",")

APP_ENV = os.getenv("APP_ENV", "development")
