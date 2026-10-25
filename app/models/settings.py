"""Application settings stored in database for persistence across restarts."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text
from app.db import Base


class AppSetting(Base):
    """Key-value store for application settings.
    
    Used for persisting user-configured API keys and other settings
    that need to survive server restarts (important for Render hosting).
    """
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)  # Encrypted/obfuscated for sensitive data
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<AppSetting {self.key}>"
