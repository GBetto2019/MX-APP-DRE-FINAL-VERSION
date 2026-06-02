"""
MX Seguros — DRE-IA | Configurações centrais do backend.
Lidas do .env via pydantic-settings.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # JWT (Settings > API > JWT Settings no dashboard Supabase)
    # Se não definido, usa a service_role_key como fallback para dev
    supabase_jwt_secret: str = ""

    # Banco direto (opcional; necessário para asyncpg)
    database_url: str = ""

    # Claude API
    anthropic_api_key: str = ""

    # App
    environment: str = "development"
    secret_key: str = "dev-secret-nao-usar-em-producao"

    @property
    def jwt_secret(self) -> str:
        """JWT secret para validar tokens do Supabase Auth."""
        return self.supabase_jwt_secret or self.supabase_service_role_key

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


cfg = Configuracoes()
