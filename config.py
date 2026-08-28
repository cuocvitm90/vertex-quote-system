"""
Root Config Compatibility Module
Exposes Settings and settings from app.config for root-level import compatibility.
"""
from app.config import Settings, settings, BASE_DIR

__all__ = ["Settings", "settings", "BASE_DIR"]
