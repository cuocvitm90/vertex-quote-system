"""
Vertex Quote Automation - Configuration Module
Uses Pydantic Settings to load and validate environment variables.
Supports both root and package-level imports.
"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Vertex Quote Automation"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BASE_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "vertex-secret-key-change-in-production"

    # AI Provider (Groq API - OpenAI Compatible)
    AI_PROVIDER: str = "groq"
    AI_BASE_URL: str = "https://api.groq.com/openai/v1"
    AI_MODEL_NAME: str = "llama-3.3-70b-versatile"
    AI_API_KEY: str = Field(default="", validation_alias="AI_API_KEY")

    # Google Drive Data Source (Vertex Standard Catalog & Reference Files)
    GDRIVE_FOLDER_ID: str = "1DPw8uKS-usaWTd7xob5EnTMZn_Vj4J5U"

    # Company Info
    COMPANY_NAME: str = "CÔNG TY CỔ PHẦN CÔNG NGHỆ VẬT TƯ VERTEX"
    COMPANY_BRAND: str = "VERTEX HVAC & MEP SOLUTIONS"
    COMPANY_HOTLINE: str = "0988.123.456"
    COMPANY_EMAIL: str = "contact@vertexhvac.vn"
    COMPANY_WEBSITE: str = "https://vertexhvac.vn"
    COMPANY_ADDRESS: str = "Khu Công Nghiệp Quang Minh, Mê Linh, Hà Nội"
    COMPANY_BANK_INFO: str = "STK: 190368686868 - Techcombank CN Hà Nội - CTCP Công Nghệ Vật Tư Vertex"

    # Pricing Defaults
    DEFAULT_VAT_RATE: float = 0.08
    DEFAULT_DISCOUNT_RATE: float = 0.05
    QUOTE_CODE_PREFIX: str = "VTX"
    QUOTE_VALIDITY_DAYS: int = 15

    # Zalo OA Settings
    ZALO_OA_ENABLED: bool = True
    ZALO_OA_ID: str = "1234567890123456789"
    ZALO_APP_ID: str = "987654321098765432"
    ZALO_SECRET_KEY: str = "your_zalo_app_secret_key"
    ZALO_OA_ACCESS_TOKEN: str = "your_zalo_oa_access_token"
    ZALO_OA_REFRESH_TOKEN: str = "your_zalo_oa_refresh_token"
    ZALO_WEBHOOK_SECRET: str = "vertex_zalo_webhook_secret_key"
    ALLOW_UNSIGNED_WEBHOOK: bool = False
    MANAGER_ZALO_USER_IDS: str = "viet_manager_zalo_id_001,tien_boss_zalo_id_002"
    MANAGER_NAMES: str = "Anh Việt (Trưởng phòng KD), Sếp Tiến (Giám đốc)"

    # Directories
    STORAGE_DIR: str = "storage"
    UPLOAD_DIR: str = "storage/uploads"
    QUOTES_DIR: str = "storage/quotes"
    DATA_DIR: str = "data"
    GDRIVE_DIR: str = "storage/reference_gdrive"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def manager_ids_list(self) -> List[str]:
        return [uid.strip() for uid in self.MANAGER_ZALO_USER_IDS.split(",") if uid.strip()]

    def setup_directories(self):
        """Ensure all storage folders exist"""
        for d in [self.STORAGE_DIR, self.UPLOAD_DIR, self.QUOTES_DIR, self.DATA_DIR, self.GDRIVE_DIR]:
            path = Path(d)
            if not path.is_absolute():
                path = BASE_DIR / path
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.setup_directories()
