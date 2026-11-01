from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://praxis:praxis@localhost:5432/praxis"
    knowledge_dir: Path = Path(__file__).resolve().parents[2] / "knowledge"
    ollama_base_url: str = "http://localhost:11434/v1"
    voice_host_url: str = "http://localhost:8001"
    llm_model: str = "gemma4:e4b"
    llm_reasoning: str = "low"  # low | none; "none" is faster but makes small models emit tool calls as text
    max_auth_attempts: int = 3
    # comma-separated lists
    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]


settings = Settings()
