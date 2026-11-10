import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_file):
    load_dotenv(env_file)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "bfb321-fintr-group28-default-secret-2026")
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "avnadmin")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "defaultdb")
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    """Configuration for local development and live debugging."""
    DEBUG = True


class TestingConfig(Config):
    """Configuration for automated test execution (pytest)."""
    TESTING = True
    DEBUG = True


class ProductionConfig(Config):
    """Configuration for production deployment (Aiven Cloud MySQL)."""
    DEBUG = False
    TESTING = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    """Returns the active configuration object based on FLASK_ENV."""
    env = os.getenv("FLASK_ENV", "development").lower()
    return config_by_name.get(env, DevelopmentConfig)
