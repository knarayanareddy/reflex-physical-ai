import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    nebius_api_key: str = os.getenv("NEBIUS_API_KEY", "mock-key")
    nebius_base_url: str = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    model_ultra: str = os.getenv("MODEL_ULTRA", "nvidia/Nemotron-3-Ultra-550b-a55b")
    model_super: str = os.getenv("MODEL_SUPER", "nvidia/nemotron-3-super-120b-a12b")
    model_nano: str = os.getenv("MODEL_NANO", "nvidia/nemotron-3-nano")
    environment: str = os.getenv("ENVIRONMENT", "development")

settings = Settings()
