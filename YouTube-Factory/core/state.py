"""State management for video production pipeline."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class VideoStatus(str, Enum):
    DRAFT = "draft"
    RESEARCHING = "researching"
    SCRIPTING = "scripting"
    GENERATING_IMAGES = "generating_images"
    COMPOSING_VIDEO = "composing_video"
    NARRATING = "narrating"
    CAPTIONING = "captioning"
    EXTRACTING_SHORTS = "extracting_shorts"
    GENERATING_THUMBNAIL = "generating_thumbnail"
    OPTIMIZING_SEO = "optimizing_seo"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class VideoProject:
    """Tracks the full state of a single video through the pipeline."""

    project_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    channel_id: str = ""
    title: str = ""
    topic: str = ""
    status: VideoStatus = VideoStatus.DRAFT
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Research phase
    research_data: dict[str, Any] = field(default_factory=dict)

    # Script phase
    script: str = ""
    script_sections: list[dict[str, str]] = field(default_factory=list)

    # Visual phase
    image_prompts: list[str] = field(default_factory=list)
    generated_images: list[str] = field(default_factory=list)  # file paths
    video_clips: list[str] = field(default_factory=list)       # file paths
    composed_video: str = ""                                     # final video path

    # Audio phase
    narration_audio: str = ""      # file path
    background_music: str = ""     # file path

    # Post-production
    captions_file: str = ""        # SRT path
    thumbnail_path: str = ""
    shorts: list[dict[str, str]] = field(default_factory=list)  # extracted shorts

    # SEO & metadata
    seo_title: str = ""
    seo_description: str = ""
    seo_tags: list[str] = field(default_factory=list)

    # Publishing
    youtube_url: str = ""
    tiktok_urls: list[str] = field(default_factory=list)
    instagram_urls: list[str] = field(default_factory=list)
    scheduled_publish_time: str = ""

    # Metrics
    quality_score: float = 0.0
    errors: list[str] = field(default_factory=list)
    agent_logs: list[dict[str, Any]] = field(default_factory=list)

    def update_status(self, new_status: VideoStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.utcnow().isoformat()

    def log_agent_action(self, agent_name: str, action: str, details: Any = None) -> None:
        self.agent_logs.append({
            "agent": agent_name,
            "action": action,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def save(self, output_dir: Path) -> Path:
        """Persist project state to JSON."""
        path = output_dir / f"{self.project_id}.json"
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, path: Path) -> VideoProject:
        """Load project state from JSON."""
        with open(path) as f:
            data = json.load(f)
        data["status"] = VideoStatus(data["status"])
        return cls(**data)


@dataclass
class ProjectState:
    """Global state tracking all active projects."""

    active_projects: dict[str, VideoProject] = field(default_factory=dict)
    completed_projects: list[str] = field(default_factory=list)

    def create_project(self, channel_id: str, topic: str) -> VideoProject:
        project = VideoProject(channel_id=channel_id, topic=topic)
        self.active_projects[project.project_id] = project
        return project

    def get_project(self, project_id: str) -> VideoProject | None:
        return self.active_projects.get(project_id)

    def complete_project(self, project_id: str) -> None:
        if project_id in self.active_projects:
            del self.active_projects[project_id]
            self.completed_projects.append(project_id)

    def get_projects_by_channel(self, channel_id: str) -> list[VideoProject]:
        return [
            p for p in self.active_projects.values()
            if p.channel_id == channel_id
        ]
