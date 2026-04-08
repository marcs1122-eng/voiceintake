"""Pipeline orchestration for video production stages."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from core.state import VideoProject, VideoStatus
from core.events import EventBus, Event

logger = logging.getLogger(__name__)


class StageResult(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineStage:
    """A single stage in the production pipeline."""
    name: str
    agent_name: str
    status_on_start: VideoStatus
    execute: Callable[[VideoProject, dict], Coroutine[Any, Any, StageResult]]
    required: bool = True
    depends_on: list[str] = field(default_factory=list)


class Pipeline:
    """Manages the ordered execution of production stages for a video project."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.stages: list[PipelineStage] = []
        self._completed_stages: dict[str, set[str]] = {}  # project_id -> completed stage names

    def add_stage(self, stage: PipelineStage) -> None:
        """Add a stage to the pipeline."""
        self.stages.append(stage)

    def _check_dependencies(self, project_id: str, stage: PipelineStage) -> bool:
        """Check if all dependencies for a stage are met."""
        completed = self._completed_stages.get(project_id, set())
        return all(dep in completed for dep in stage.depends_on)

    async def run(self, project: VideoProject, context: dict[str, Any]) -> bool:
        """Execute all pipeline stages for a project in order."""
        project_id = project.project_id
        self._completed_stages[project_id] = set()
        all_success = True

        logger.info(f"Starting pipeline for project {project_id}: {project.topic}")

        for stage in self.stages:
            if not self._check_dependencies(project_id, stage):
                logger.warning(
                    f"Skipping stage '{stage.name}' - dependencies not met: {stage.depends_on}"
                )
                if stage.required:
                    all_success = False
                    break
                continue

            project.update_status(stage.status_on_start)
            logger.info(f"[{project_id}] Running stage: {stage.name}")

            await self.event_bus.emit(Event(
                name="stage.started",
                source=stage.agent_name,
                data={"project_id": project_id, "stage": stage.name},
            ))

            try:
                result = await stage.execute(project, context)
            except Exception as e:
                logger.error(f"[{project_id}] Stage '{stage.name}' crashed: {e}")
                project.add_error(f"Stage '{stage.name}' error: {str(e)}")
                result = StageResult.FAILED

            if result == StageResult.SUCCESS:
                self._completed_stages[project_id].add(stage.name)
                project.log_agent_action(stage.agent_name, f"completed_{stage.name}")
                await self.event_bus.emit(Event(
                    name="stage.completed",
                    source=stage.agent_name,
                    data={"project_id": project_id, "stage": stage.name},
                ))
            elif result == StageResult.FAILED:
                project.add_error(f"Stage '{stage.name}' failed")
                await self.event_bus.emit(Event(
                    name="stage.failed",
                    source=stage.agent_name,
                    data={"project_id": project_id, "stage": stage.name},
                ))
                if stage.required:
                    logger.error(f"[{project_id}] Required stage '{stage.name}' failed. Aborting.")
                    all_success = False
                    break
            else:
                logger.info(f"[{project_id}] Stage '{stage.name}' skipped")

        # Cleanup
        if project_id in self._completed_stages:
            del self._completed_stages[project_id]

        return all_success
