from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    backend_secret_key: str
    flag_hmac_secret: str = ""
    app_env: str = "development"
    log_level: str = "INFO"
    session_ttl_hours: int = 12
    admin_username: str = "admin"
    admin_password: str = ""
    @property
    def effective_flag_hmac_secret(self) -> str:
        return self.flag_hmac_secret or self.backend_secret_key

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()  # type: ignore[call-arg]  # Values are loaded from environment variables.
