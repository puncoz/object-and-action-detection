"""Configuration settings for Factory Action Console."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App settings
    app_name: str = "Factory Action Console"
    debug: bool = False

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000

    # Database credentials
    db_type: str = "sqlite"  # "sqlite" or "postgresql"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "factory_console"
    db_user: str = ""
    db_password: str = ""

    @property
    def database_url(self) -> str:
        """Build database URL from credentials."""
        if self.db_type == "postgresql":
            return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        return "sqlite+aiosqlite:///./data/factory.db"

    # Storage paths
    data_dir: Path = Path("./data")
    snapshots_dir: Path = Path("./data/snapshots")
    clips_dir: Path = Path("./data/clips")

    # OpenAI settings
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"   # Fast & cheap; override with gpt-4o for accuracy
    openai_max_tokens: int = 150         # JSON response is ~80 tokens; cap tightly

    # Video settings
    default_fps: int = 15
    mjpeg_quality: int = 70
    frame_width: int = 1280
    frame_height: int = 720

    # Detection settings
    detection_interval_ms: int = 500   # Min gap between LLM calls (ms)
    confidence_threshold: float = 0.6
    consecutive_frames_required: int = 2

    # Ring buffer settings
    ring_buffer_duration_sec: int = 30
    clip_before_sec: int = 10
    clip_after_sec: int = 10

    # CORS settings
    cors_origins: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.clips_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
