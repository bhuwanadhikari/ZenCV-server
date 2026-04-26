from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_key: str = Field(alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    llm_input_cost_per_1m_tokens: Optional[float] = Field(
        default=None, alias="LLM_INPUT_COST_PER_1M_TOKENS"
    )
    llm_output_cost_per_1m_tokens: Optional[float] = Field(
        default=None, alias="LLM_OUTPUT_COST_PER_1M_TOKENS"
    )
    MY_STORY_TXT: Path = Field(default=Path("data/user-profile/my_story.txt"), alias="MY_STORY_TXT")
    
    # Google OAuth Configuration
    google_client_id: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="http://localhost:8000/api/auth/google/callback", alias="GOOGLE_REDIRECT_URI")
    
    # JWT Configuration
    secret_key: str = Field(default="your-secret-key-change-in-production", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Database
    database_url: str = Field(default="sqlite:///./intellicv.db", alias="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing_fields = [
            ".".join(str(part) for part in error["loc"])
            for error in exc.errors()
            if error["type"] == "missing"
        ]
        if missing_fields:
            missing_fields_text = ", ".join(missing_fields)
            raise ValueError(
                "Missing required environment variables: "
                f"{missing_fields_text}. Create a `.env` file in the project root, "
                "for example by copying `.env.example`, and set the required values."
            ) from exc
        raise
