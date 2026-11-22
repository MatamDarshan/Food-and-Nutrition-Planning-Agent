"""
config/settings.py
------------------
Centralized application settings using pydantic-settings.
Consistently uses GOOGLE_API_KEY across all agent nodes and backend services,
automatically loaded from the local .env file.
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Gemini API configuration — centralized on GOOGLE_API_KEY
    google_api_key: str = Field(
        default="",
        validation_alias="GOOGLE_API_KEY",
        description="Google Gemini API Key",
    )

    # Gemini model selection.
    # gemini-2.0-flash was retired by Google in 2026 (404 NOT_FOUND), so the
    # officially available "flash-lite" alias is used by default. It supports
    # tool calling and is the fastest generally-available flash model.
    model_name: str = Field(
        default="gemini-flash-lite-latest",
        description="Selected Gemini model identifier",
    )

    temperature: float = Field(
        default=0.2,
        description="Model temperature for reasoning",
    )

    # Gemini call resilience: bound latency and retry transient failures.
    max_output_tokens: int = Field(
        default=8192,
        description="Maximum tokens Gemini may generate per response",
    )

    request_timeout: float = Field(
        default=120.0,
        description="Per-request timeout in seconds for Gemini calls",
    )

    max_retries: int = Field(
        default=2,
        description="Retries for transient Gemini/network failures",
    )

    # Agent revision guard
    max_revisions: int = Field(
        default=2,
        description="Maximum retry attempts on validation failure",
    )

    calorie_deviation_threshold: float = Field(
        default=0.15,
        description="Acceptable calorie target deviation percentage (+/- 15%)",
    )

    # Paths
    food_csv_path: Path = Field(
        default=BASE_DIR / "data" / "food_data.csv",
        description="Path to Indian food database CSV",
    )

    def model_post_init(self, __context) -> None:
        """Post-initialization to normalize key and sync environment cleanly."""
        key = (self.google_api_key or "").strip()

        # If GOOGLE_API_KEY was not found, check fallback GEMINI_API_KEY in env
        if not key or key in ("your_gemini_api_key_here", "your_api_key_here", "AIzaSy..."):
            key = (os.environ.get("GEMINI_API_KEY") or "").strip()

        # Check local key files (e.g., .api key, .api_key, .api)
        if not key or key in ("your_gemini_api_key_here", "your_api_key_here", "AIzaSy..."):
            for fname in [".api key", ".api_key", ".apikey", ".api", "api_key.txt"]:
                p = BASE_DIR / fname
                if p.exists():
                    try:
                        content = p.read_text(encoding="utf-8").strip()
                        if content and not content.startswith("#"):
                            first_line = content.splitlines()[0].strip().strip("'\"")
                            if first_line and len(first_line) > 10:
                                key = first_line
                                break
                    except Exception:
                        pass

        # Discard placeholder strings
        if key in ("your_gemini_api_key_here", "your_api_key_here", "AIzaSy..."):
            key = ""

        self.google_api_key = key

        # Consistently set only GOOGLE_API_KEY in os.environ and remove GEMINI_API_KEY
        # to prevent conflicting duplicate key warnings from langchain-google-genai
        if self.google_api_key:
            os.environ["GOOGLE_API_KEY"] = self.google_api_key
        else:
            os.environ.pop("GOOGLE_API_KEY", None)

        os.environ.pop("GEMINI_API_KEY", None)

    @property
    def api_key(self) -> str:
        """Return the centralized Google API key."""
        return self.google_api_key


# Centralized singleton settings instance
settings = Settings()
