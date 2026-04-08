"""File management utilities for media assets."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class FileManager:
    """Handles file I/O for video project assets."""

    def __init__(self, base_output_dir: str = "./output") -> None:
        self.base_dir = Path(base_output_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def project_dir(self, channel_id: str, project_id: str) -> Path:
        """Get or create the directory for a specific project."""
        d = self.base_dir / channel_id / project_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_text(self, channel_id: str, project_id: str, filename: str, content: str) -> Path:
        """Save text content to a project file."""
        path = self.project_dir(channel_id, project_id) / filename
        path.write_text(content, encoding="utf-8")
        return path

    def save_bytes(self, channel_id: str, project_id: str, filename: str, data: bytes) -> Path:
        """Save binary content (images, audio, video) to a project file."""
        path = self.project_dir(channel_id, project_id) / filename
        path.write_bytes(data)
        return path

    def read_text(self, channel_id: str, project_id: str, filename: str) -> str:
        """Read text content from a project file."""
        path = self.project_dir(channel_id, project_id) / filename
        return path.read_text(encoding="utf-8")

    def list_files(self, channel_id: str, project_id: str, pattern: str = "*") -> list[Path]:
        """List files in a project directory matching a glob pattern."""
        d = self.project_dir(channel_id, project_id)
        return sorted(d.glob(pattern))

    def cleanup_project(self, channel_id: str, project_id: str) -> None:
        """Remove all files for a completed/failed project."""
        d = self.base_dir / channel_id / project_id
        if d.exists():
            shutil.rmtree(d)
