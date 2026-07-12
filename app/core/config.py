from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SpecPulse"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://specpulse:specpulse@localhost:5432/specpulse"
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
