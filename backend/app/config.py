import os

from dotenv import load_dotenv

load_dotenv()


APP_ENV = os.getenv("APP_ENV", "development")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://contentuser:contentpass@postgres:5432/contentdb",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
STORAGE_PATH = os.getenv("STORAGE_PATH", "/app/storage")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
MEDIA_RETENTION_DAYS = int(os.getenv("MEDIA_RETENTION_DAYS", "30"))
