from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    redis_url: str
    postgres_url: str

    llm_base_url: str
    llm_api_key: str
    llm_model: str = "qwen/qwen3-coder"
    llm_max_tokens: int = 2048

    github_app_id: str
    github_app_private_key: str
    github_installation_id: str

    # PAT for reading public repos/releases (avoids 60 req/hr rate limit)
    # Generate at: GitHub → Settings → Developer settings → PATs (classic), scope: public_repo
    github_token: str | None = None

    # e2b sandbox API key — https://e2b.dev/dashboard → API Keys
    e2b_api_key: str | None = None

    sandbox_backend: str = "e2b"

    enable_training: bool = True
    enable_registry_triggers: bool = True
    enable_regression_checks: bool = True
    enable_streaming: bool = True


settings = Settings()
