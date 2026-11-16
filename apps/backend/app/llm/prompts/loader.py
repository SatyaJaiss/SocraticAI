"""YAML prompt-template loading with ``string.Template`` substitution."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from string import Template

import yaml

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError

# Default locations to search for prompt files
_PROJECT_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_DIRS = [
    _PROJECT_ROOT / "configs" / "prompts",
    Path(__file__).resolve().parent,
]


@cache
def _load_yaml(name: str) -> dict:
    settings = get_settings()
    search_dirs = [settings.prompts_dir, *_DEFAULT_DIRS]
    path: Path | None = None
    for directory in search_dirs:
        candidate = Path(directory) / f"{name}.yaml"
        if candidate.exists():
            path = candidate
            break

    if path is None:
        raise ConfigurationError(f"Prompt template not found: {name}.yaml")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "system" not in data:
        raise ConfigurationError(f"Prompt template {path.name} must define a 'system' key")
    return data


def get_prompt(name: str) -> str:
    """Return the raw (un-substituted) system prompt for an agent."""
    return _load_yaml(name)["system"]


def render_prompt(name: str, **kwargs: object) -> str:
    """Return the system prompt with ``$key`` placeholders substituted.

    Missing placeholders are left intact via ``safe_substitute`` so a typo never
    crashes a prompt build.
    """
    return Template(get_prompt(name)).safe_substitute(**kwargs)
