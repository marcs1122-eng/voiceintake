"""Shorts Extractor Agent - extracts vertical short clips from long-form video."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class ShortsExtractorAgent(BaseAgent):
    """Extracts engaging short-form clips from the full video.

    Analyzes the script to identify the most hook-worthy moments, then uses
    ffmpeg to extract and reformat them as vertical 9:16 shorts for YouTube
    Shorts, TikTok, and Instagram Reels.
    """

    name = "shorts_extractor"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["composed_video", "script_sections"]):
            raise ValueError("Composed video and script required before shorts extraction")

        api_keys = context["api_keys"]
        file_manager = context["file_manager"]
        channel_cfg = self.get_channel_config(project)
        shorts_cfg = channel_cfg.get("content", {}).get("shorts", {})

        extract_count = shorts_cfg.get("extract_count", 3)
        target_duration = shorts_cfg.get("target_duration", 45)
        max_duration = shorts_cfg.get("max_duration", 60)
        style = shorts_cfg.get("style", "cliffhanger_teaser")

        self.logger.info(f"Extracting {extract_count} shorts (style: {style})")

        # Use LLM to identify best moments for shorts
        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        sections_summary = json.dumps(project.script_sections, indent=2)

        analysis_prompt = f"""Analyze this video script and identify the {extract_count} best moments
to extract as short-form vertical videos ({target_duration}s each, max {max_duration}s).

Style: {style}
Channel tone: {channel_cfg.get('tone', 'engaging')}

Script sections:
{sections_summary}

For each short, provide:
1. The section index to extract from
2. Approximate start time (based on section ordering and estimated pacing)
3. Duration in seconds
4. A catchy title/hook for the short
5. Why this moment works as a standalone short

Output as JSON array:
[
  {{
    "section_index": 0,
    "start_seconds": 30,
    "duration": {target_duration},
    "title": "Catchy short title",
    "hook_text": "Opening text overlay for the short",
    "reason": "Why this works"
  }}
]"""

        async def _analyze():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=2048,
                messages=[{"role": "user", "content": analysis_prompt}],
            )
            return response.content[0].text

        raw = await self.retry(_analyze)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        short_specs = json.loads(raw.strip())

        # Extract each short using ffmpeg
        extracted_shorts = []
        project_dir = file_manager.project_dir(project.channel_id, project.project_id)

        for i, spec in enumerate(short_specs[:extract_count]):
            output_path = project_dir / f"short_{i:02d}.mp4"
            start = spec.get("start_seconds", 0)
            duration = min(spec.get("duration", target_duration), max_duration)

            try:
                # Extract and convert to vertical 9:16
                cmd = [
                    "ffmpeg", "-y",
                    "-i", project.composed_video,
                    "-ss", str(start),
                    "-t", str(duration),
                    "-vf", "crop=ih*9/16:ih,scale=1080:1920",
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    str(output_path),
                ]

                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()

                if proc.returncode == 0:
                    extracted_shorts.append({
                        "path": str(output_path),
                        "title": spec.get("title", f"Short {i + 1}"),
                        "hook_text": spec.get("hook_text", ""),
                        "duration": duration,
                    })
                else:
                    self.logger.warning(f"Short {i} extraction failed: {stderr.decode()[:200]}")

            except Exception as e:
                self.logger.error(f"Short {i} extraction error: {e}")

        project.shorts = extracted_shorts

        project.log_agent_action(self.name, "shorts_extracted", {
            "requested": extract_count,
            "extracted": len(extracted_shorts),
        })

        await self.emit("shorts.extracted", {
            "project_id": project.project_id,
            "count": len(extracted_shorts),
        })

        self.logger.info(f"Extracted {len(extracted_shorts)}/{extract_count} shorts")
        return {"shorts": extracted_shorts}
