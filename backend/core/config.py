from __future__ import annotations

from typing import Optional

from pydantic import EmailStr
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
	# --- NUEVA CONFIGURACIÓN MICROSOFT (EXCHANGE ONLINE) ---
	MICROSOFT_CLIENT_ID: str = ""
	MICROSOFT_TENANT_ID: str = ""
	MICROSOFT_CLIENT_SECRET: str = ""
	
	# Mantenemos estas para no romper la lógica visual y de prefijos
	SMTP_FROM: Optional[EmailStr] = "sicae@ipn.mx"
	SMTP_SUBJECT_PREFIX: str = "SiCAE"

	# DB (se mantienen para compatibilidad con entorno existente)
	DB_USER: str = ""
	DB_PASSWORD: str = ""
	DB_HOST: str = ""
	DB_PORT: int = 1433
	DB_NAME: str = ""
	DB_DRIVER: str = "ODBC Driver 17 for SQL Server"

	model_config = {
		"env_file": ".env",
		"case_sensitive": False,
		"extra": "ignore"  # Ignorar variables no declaradas futuras
	}

	@property
	def effective_from(self) -> str:
		# Ahora el remitente oficial siempre será SMTP_FROM (sicae@ipn.mx)
		return self.SMTP_FROM or "sicae@ipn.mx"

@lru_cache()
def get_settings() -> Settings:
	return Settings()  # Carga desde .env

settings = get_settings()
