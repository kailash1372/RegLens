"""Configuration loaded from environment without exposing secrets."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for local fixture and future live-provider modes."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_provider: str = Field(default="fixture", validation_alias="REGLENS_DATA_PROVIDER")
    database_path: Path = Field(
        default=Path("backend/data/reglens.db"), validation_alias="REGLENS_DATABASE_PATH"
    )
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="stealth/ox-alpha", validation_alias="OPENROUTER_MODEL")
    brightdata_api_token: str | None = Field(default=None, validation_alias="BRIGHTDATA_API_TOKEN")
    brightdata_api_base_url: str = Field(
        default="https://api.brightdata.com", validation_alias="BRIGHTDATA_API_BASE_URL"
    )
    brightdata_trigger_path: str = Field(
        default="/dca/trigger", validation_alias="BRIGHTDATA_TRIGGER_PATH"
    )
    brightdata_poll_path: str = Field(
        default="/dca/dataset", validation_alias="BRIGHTDATA_POLL_PATH"
    )
    brightdata_output_path: str = Field(
        default="/dca/dataset", validation_alias="BRIGHTDATA_OUTPUT_PATH"
    )
    brightdata_poll_interval_seconds: float = Field(
        default=2.0, ge=0, validation_alias="BRIGHTDATA_POLL_INTERVAL_SECONDS"
    )
    brightdata_max_poll_attempts: int = Field(
        default=20, ge=1, validation_alias="BRIGHTDATA_MAX_POLL_ATTEMPTS"
    )
    brightdata_collector_alani: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_ALANI"
    )
    brightdata_collector_celsius: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_CELSIUS"
    )
    brightdata_collector_c4: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_C4"
    )
    brightdata_collector_bloom: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_BLOOM"
    )
    brightdata_collector_red_bull: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_RED_BULL"
    )
    brightdata_collector_brachs: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_BRACHS"
    )
    brightdata_collector_fanta_sa: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_FANTA_SA"
    )
    brightdata_collector_fanta_ca: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_FANTA_CA"
    )
    brightdata_collector_reign: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_REIGN"
    )
    brightdata_collector_mountain_dew: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_MOUNTAIN_DEW_CODE_RED"
    )
    brightdata_collector_doritos: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_DORITOS_NACHO_CHEESE"
    )
    brightdata_collector_cheetos: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_CHEETOS_CRUNCHY"
    )
    brightdata_collector_maggi: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_MAGGI_MASALA"
    )
    brightdata_collector_nongshim: str | None = Field(
        default=None, validation_alias="BRIGHTDATA_COLLECTOR_NONGSHIM_SHIN_BIG_BOWL"
    )

    @field_validator("data_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        """Limit providers to modes deliberately supported by this MVP."""
        normalized = value.strip().lower()
        if normalized not in {"fixture", "brightdata"}:
            message = "REGLENS_DATA_PROVIDER must be 'fixture' or 'brightdata'."
            raise ValueError(message)
        return normalized

    @property
    def brightdata_collectors(self) -> dict[str, str]:
        """Return configured collector IDs without exposing the API token."""
        configured = {
            "alani-nu-cotton-candy": self.brightdata_collector_alani,
            "celsius-sparkling-orange": self.brightdata_collector_celsius,
            "c4-frozen-bombsicle": self.brightdata_collector_c4,
            "bloom-raspberry-lemon": self.brightdata_collector_bloom,
            "red-bull-original": self.brightdata_collector_red_bull,
            "brachs-classic-jelly-beans": self.brightdata_collector_brachs,
            "fanta-orange-sa": self.brightdata_collector_fanta_sa,
            "fanta-orange-ca": self.brightdata_collector_fanta_ca,
            "reign-orange-dreamsicle": self.brightdata_collector_reign,
            "mountain-dew-code-red": self.brightdata_collector_mountain_dew,
            "doritos-nacho-cheese": self.brightdata_collector_doritos,
            "cheetos-crunchy": self.brightdata_collector_cheetos,
            "maggi-masala-noodles": self.brightdata_collector_maggi,
            "nongshim-shin-big-bowl": self.brightdata_collector_nongshim,
        }
        return {
            product_id: collector_id
            for product_id, collector_id in configured.items()
            if collector_id
        }


def get_settings() -> Settings:
    """Return the current settings instance for dependency injection."""
    return Settings()
