# core/config.py
import os
from typing import Optional


class Settings:
    """Centralized configuration loaded from environment variables."""
    
    # Required settings
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY")
    
    # Optional settings with defaults
    LOG_RETENTION_DAYS: int = int(os.getenv("LOG_RETENTION_DAYS", "30"))
    RATE_LIMIT_WINDOW_HOURS: int = int(os.getenv("RATE_LIMIT_WINDOW_HOURS", "1"))
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "50"))
    PDF_PROCESSING_TIMEOUT: int = int(os.getenv("PDF_PROCESSING_TIMEOUT", "30"))
    
    def validate(self) -> None:
        """Validate that all required settings are present."""
        missing = []
        
        if not self.DATABASE_URL:
            missing.append("DATABASE_URL")
        if not self.JWT_SECRET_KEY:
            missing.append("JWT_SECRET_KEY")
            
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        # Additional validation
        if not self.DATABASE_URL.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")
        
        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")


# Global settings instance
settings = Settings()