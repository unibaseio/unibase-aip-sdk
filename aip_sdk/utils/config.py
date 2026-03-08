"""Configuration management utilities."""

import os


def get_default_aip_endpoint() -> str:
    """Get default AIP endpoint from deployment config or environment."""
    env_url = os.environ.get("AIP_ENDPOINT")
    if env_url:
        return env_url

    try:
        from aip.core.config import get_config
        config = get_config()
        return config.aip.public_url
    except Exception:
        return "http://api.aip.unibase.com"
