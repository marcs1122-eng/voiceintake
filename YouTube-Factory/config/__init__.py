"""Configuration loader for YouTube AI Factory."""

import os
from pathlib import Path
from typing import Any

import yaml


CONFIG_DIR = Path(__file__).parent
PROJECT_ROOT = CONFIG_DIR.parent


def load_yaml(filename: str) -> dict[str, Any]:
    """Load a YAML config file from the config directory."""
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def load_channels() -> dict[str, Any]:
    """Load channel configurations with defaults applied."""
    data = load_yaml("channels.yaml")
    defaults = data.get("defaults", {})
    channels = {}
    for channel_id, channel_cfg in data.get("channels", {}).items():
        merged = {**defaults, **channel_cfg}
        merged["channel_id"] = channel_id
        channels[channel_id] = merged
    return channels


def load_api_keys() -> dict[str, Any]:
    """Load API keys from api_keys.yaml (must exist, not the example)."""
    path = CONFIG_DIR / "api_keys.yaml"
    if not path.exists():
        raise FileNotFoundError(
            "api_keys.yaml not found. Copy api_keys.yaml.example to api_keys.yaml "
            "and fill in your API keys."
        )
    with open(path) as f:
        return yaml.safe_load(f)


def get_channel_ids() -> list[str]:
    """Return list of configured channel IDs."""
    data = load_yaml("channels.yaml")
    return list(data.get("channels", {}).keys())


def get_output_dir(channel_id: str) -> Path:
    """Get output directory for a channel, creating it if needed."""
    out = PROJECT_ROOT / "output" / channel_id
    out.mkdir(parents=True, exist_ok=True)
    return out
