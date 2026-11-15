"""
config/settings.py
------------------
Central application configuration using pydantic-settings.
Reads values from environment variables or a local .env file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Gemini API configuration
    gemini_api_key: str = Field(
        default="",
        validation_alias="GEMINI_API_KEY",
        description="Google Gemini API Key"
    )
    google_api_key: str = Field(
        default="",
        validation_alias="GOOGLE_API_KEY",
        description="Fallback alias for Gemini API key"
    )
    model_name: str = Field(
        default="gemini-2.0-flash",
        description="Default Gemini model"
    )
    temperature: float = Field(
        default=0.2,
        description="Model temperature for reasoning"
    )

    # Agent configuration
    max_revisions: int = Field(
        default=2,
        description="Maximum retry attempts on validation failure"
    )
    calorie_deviation_threshold: float = Field(
        default=0.15,
        description="Acceptable calorie target deviation percentage (+/- 15%)"
    )

    # Paths
    food_csv_path: Path = Field(
        default=BASE_DIR / "data" / "food_data.csv",
        description="Path to Indian food database CSV"
    )

    @property
    def api_key(self) -> str:
        """Return the effective API key, checking environment, .env, and .api key files."""
        # 1. Check direct settings / environment variables
        key = (self.gemini_api_key or self.google_api_key or "").strip()
        
        # 2. If not found, check dedicated key files (e.g. .api key, .api_key, .api)
        if not key or key in ("your_gemini_api_key_here", "your_api_key_here", "AIzaSy..."):
            for fname in [".api key", ".api_key", ".apikey", ".api", "api_key.txt", "apikey.txt"]:
                key_file = BASE_DIR / fname
                if key_file.exists():
                    try:
                        file_content = key_file.read_text(encoding="utf-8").strip()
                        if file_content and not file_content.startswith("#"):
                            key = file_content.splitlines()[0].strip().strip("'\"")
                            if key:
                                break
                    except Exception:
                        pass

        # Filter out placeholder strings
        if key in ("your_gemini_api_key_here", "your_api_key_here", "AIzaSy..."):
            return ""
        return key

settings = Settings()
