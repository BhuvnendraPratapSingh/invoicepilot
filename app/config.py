"""Application configuration loaded from environment / .env file."""

from datetime import date, datetime
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    # Application
    app_env: str = "demo"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    demo_mode: bool = True
    demo_business_date: date = date(2026, 3, 15)

    # Database
    database_url: str = "sqlite:///./data/invoicepilot.db"

    # Storage
    upload_dir: str = "./data/uploads"
    max_file_size_mb: int = 10
    max_pages: int = 20

    # Workers
    worker_count: int = 2

    # Optional AI extraction (for field extraction, not OCR)
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"
    ai_extraction_enabled: bool = False

    # ─── Cloud OCR API Keys (user-provided, billed to user) ───
    # Users can configure one of these to enable cloud-based OCR for scanned PDFs
    # Priority: OpenAI > Anthropic > Google (first available key is used)
    ocr_openai_api_key: Optional[str] = None
    ocr_anthropic_api_key: Optional[str] = None
    ocr_google_api_key: Optional[str] = None
    
    # OCR provider preference (auto, openai, anthropic, google, tesseract)
    # "auto" uses first available cloud API, falls back to Tesseract
    ocr_provider: str = "auto"

    # Policy
    policy_version: str = "demo-policy-v1"
    currency: str = "USD"
    arithmetic_tolerance_cents: int = 1  # $0.01
    po_overage_pct: str = "0.01"  # 1%
    po_overage_max_cents: int = 5000  # $50.00

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def page_images_path(self) -> Path:
        p = Path(self.upload_dir) / "page_images"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_business_date(self) -> date:
        """Return the demo business date if in demo mode, else today."""
        if self.demo_mode:
            return self.demo_business_date
        return date.today()

    def get_ocr_provider_info(self) -> dict:
        """Get information about configured OCR providers."""
        providers = []
        
        if self.ocr_openai_api_key:
            providers.append({
                "name": "openai",
                "display": "OpenAI GPT-4 Vision",
                "configured": True,
                "key_preview": self.ocr_openai_api_key[:8] + "..." if len(self.ocr_openai_api_key) > 8 else "***"
            })
        
        if self.ocr_anthropic_api_key:
            providers.append({
                "name": "anthropic",
                "display": "Anthropic Claude Vision",
                "configured": True,
                "key_preview": self.ocr_anthropic_api_key[:8] + "..." if len(self.ocr_anthropic_api_key) > 8 else "***"
            })
        
        if self.ocr_google_api_key:
            providers.append({
                "name": "google",
                "display": "Google Gemini Vision",
                "configured": True,
                "key_preview": self.ocr_google_api_key[:8] + "..." if len(self.ocr_google_api_key) > 8 else "***"
            })
        
        # Check local Tesseract
        try:
            from app.services.ocr import check_tesseract
            tesseract_available = check_tesseract()
        except:
            tesseract_available = False
        
        providers.append({
            "name": "tesseract",
            "display": "Tesseract (Local)",
            "configured": tesseract_available,
            "key_preview": "N/A (local install)"
        })
        
        return {
            "providers": providers,
            "active_provider": self.ocr_provider,
            "has_cloud_ocr": bool(self.ocr_openai_api_key or self.ocr_anthropic_api_key or self.ocr_google_api_key),
        }


settings = Settings()


# ─── Persistent OCR Key Management (Database-backed for Render) ───
# Keys are stored in the database so they survive server restarts

def _get_db_session():
    """Get a database session for settings operations."""
    from app.db import SessionLocal
    return SessionLocal()


def set_ocr_api_key(provider: str, key: str) -> bool:
    """Set an OCR API key persistently in the database. Returns True if valid provider."""
    if provider not in ("openai", "anthropic", "google"):
        return False
    
    from app.models.settings import AppSetting
    
    db = _get_db_session()
    try:
        setting_key = f"ocr_api_key_{provider}"
        existing = db.query(AppSetting).filter(AppSetting.key == setting_key).first()
        
        if key:
            # Simple obfuscation (not encryption - for demo purposes)
            # In production, use proper encryption with a secret key
            import base64
            obfuscated = base64.b64encode(key.encode()).decode()
            
            if existing:
                existing.value = obfuscated
            else:
                db.add(AppSetting(key=setting_key, value=obfuscated))
        else:
            # Clear the key
            if existing:
                db.delete(existing)
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Error saving OCR key: {e}")
        return False
    finally:
        db.close()


def get_ocr_api_key(provider: str) -> Optional[str]:
    """Get OCR API key from database, falling back to environment config."""
    if provider not in ("openai", "anthropic", "google"):
        return None
    
    # First check database (user-configured at runtime)
    from app.models.settings import AppSetting
    
    try:
        db = _get_db_session()
        setting_key = f"ocr_api_key_{provider}"
        setting = db.query(AppSetting).filter(AppSetting.key == setting_key).first()
        db.close()
        
        if setting and setting.value:
            # Deobfuscate
            import base64
            try:
                return base64.b64decode(setting.value.encode()).decode()
            except:
                pass
    except Exception:
        pass  # Database might not be initialized yet
    
    # Fall back to environment config
    if provider == "openai":
        return settings.ocr_openai_api_key
    elif provider == "anthropic":
        return settings.ocr_anthropic_api_key
    elif provider == "google":
        return settings.ocr_google_api_key
    return None


def get_active_ocr_provider() -> Optional[str]:
    """Determine which OCR provider to use based on config and available keys."""
    pref = settings.ocr_provider.lower()
    
    # If specific provider requested, check if key available
    if pref in ("openai", "anthropic", "google"):
        if get_ocr_api_key(pref):
            return pref
        return None  # Requested provider but no key
    
    if pref == "tesseract":
        return "tesseract"
    
    # Auto mode: try cloud providers in order, then tesseract
    if pref == "auto":
        if get_ocr_api_key("openai"):
            return "openai"
        if get_ocr_api_key("anthropic"):
            return "anthropic"
        if get_ocr_api_key("google"):
            return "google"
        # Fall back to tesseract
        return "tesseract"
    
    return "tesseract"
