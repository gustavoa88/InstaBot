import os

from dotenv import load_dotenv

load_dotenv()


APP_ENV = os.getenv("APP_ENV", "development")
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "dev-admin-token")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://contentuser:contentpass@postgres:5432/contentdb",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "1600"))
OPENAI_VERBOSITY = os.getenv("OPENAI_VERBOSITY", "low")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "minimal")
OPENAI_DAILY_REQUEST_LIMIT = int(os.getenv("OPENAI_DAILY_REQUEST_LIMIT", "20"))
OPENAI_CARROSSEL_REQUEST_LIMIT = int(os.getenv("OPENAI_CARROSSEL_REQUEST_LIMIT", "3"))
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1-mini")
OPENAI_IMAGE_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1536")
OPENAI_IMAGE_DAILY_REQUEST_LIMIT = int(os.getenv("OPENAI_IMAGE_DAILY_REQUEST_LIMIT", "10"))
OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT = int(os.getenv("OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT", "7"))
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_USER_ID = os.getenv("INSTAGRAM_USER_ID", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
STORAGE_PATH = os.getenv("STORAGE_PATH", "/app/storage")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")
MEDIA_RETENTION_DAYS = int(os.getenv("MEDIA_RETENTION_DAYS", "30"))
