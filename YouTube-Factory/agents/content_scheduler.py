"""Content Scheduler Agent - manages publishing schedule across channels."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from agents.base import BaseAgent
from core.state import VideoProject


class ContentSchedulerAgent(BaseAgent):
    """Manages content scheduling based on channel-specific publishing cadence.

    Determines optimal publish times based on the channel's configured schedule,
    avoids conflicts with other scheduled content, and sets publish timestamps.
    """

    name = "content_scheduler"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        channel_cfg = self.get_channel_config(project)
        schedule_cfg = channel_cfg.get("schedule", {})
        timezone_str = schedule_cfg.get("timezone", "UTC")
        tz = ZoneInfo(timezone_str)

        # Determine if this is long-form or shorts content
        is_short = bool(project.shorts and not project.composed_video)
        content_type = "shorts" if is_short else "long_form"
        type_schedule = schedule_cfg.get(content_type, {})

        publish_days = type_schedule.get("days", [])
        publish_time_str = type_schedule.get("time", "12:00")

        self.logger.info(
            f"Scheduling {content_type} for channel '{project.channel_id}' "
            f"(days: {publish_days}, time: {publish_time_str})"
        )

        # Find the next available publish slot
        now = datetime.now(tz)
        publish_hour, publish_minute = map(int, publish_time_str.split(":"))

        # Get already scheduled times from context to avoid conflicts
        scheduled_times: set[str] = context.get("scheduled_times", set())

        next_slot = self._find_next_slot(
            now=now,
            publish_days=publish_days,
            hour=publish_hour,
            minute=publish_minute,
            tz=tz,
            exclude_times=scheduled_times,
        )

        publish_iso = next_slot.isoformat()
        project.scheduled_publish_time = publish_iso

        # Register this slot to prevent conflicts
        scheduled_times.add(publish_iso)
        context["scheduled_times"] = scheduled_times

        project.log_agent_action(self.name, "scheduled", {
            "publish_time": publish_iso,
            "content_type": content_type,
            "timezone": timezone_str,
        })

        await self.emit("content.scheduled", {
            "project_id": project.project_id,
            "publish_time": publish_iso,
        })

        self.logger.info(f"Scheduled for: {publish_iso}")
        return {"scheduled_publish_time": publish_iso, "content_type": content_type}

    def _find_next_slot(
        self,
        now: datetime,
        publish_days: list[str],
        hour: int,
        minute: int,
        tz: ZoneInfo,
        exclude_times: set[str],
        max_days_ahead: int = 30,
    ) -> datetime:
        """Find the next available publish slot matching the schedule."""
        day_names = [
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        ]
        target_weekdays = set()
        for day in publish_days:
            day_lower = day.lower()
            if day_lower in day_names:
                target_weekdays.add(day_names.index(day_lower))

        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If today's slot already passed, start from tomorrow
        if candidate <= now:
            candidate += timedelta(days=1)

        for _ in range(max_days_ahead):
            if candidate.weekday() in target_weekdays:
                if candidate.isoformat() not in exclude_times:
                    return candidate
            candidate += timedelta(days=1)

        # Fallback: next available day at the configured time
        return now + timedelta(days=1)
