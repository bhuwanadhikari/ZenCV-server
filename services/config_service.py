from functools import lru_cache
from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_key: str = Field(alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL")
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_timeout_seconds: int = Field(default=60, alias="LLM_TIMEOUT_SECONDS")
    my_story_json_path: Path = Field(default=Path("data/my_story.json"), alias="MY_STORY_JSON_PATH")

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
