"""
Configuration module for Hack My Contract.

Loads application settings from environment variables and .env file
using pydantic-settings for validation and type coercion.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        openai_api_key: OpenAI API key for LLM-powered adversarial analysis.
        openai_model: The OpenAI model to use for analysis (default: gpt-4o-mini).
        etherscan_api_key: Etherscan API key for fetching verified contract source code.
        xlayer_explorer_url: Base URL for the OKX X Layer block explorer API.
        app_name: Display name of the application.
        debug: Enable debug mode for verbose logging and error details.
    """

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    etherscan_api_key: str = ""
    xlayer_explorer_url: str = "https://www.okx.com/explorer/xlayer/api"
    app_name: str = "Hack My Contract"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """Create and return a Settings instance.

    Returns:
        Settings: Validated application settings.
    """
    return Settings()
