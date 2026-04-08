"""Caption Generator Agent - creates SRT subtitles from narration."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class CaptionGeneratorAgent(BaseAgent):
    """Generates SRT caption files from the narration script.

    Creates precisely timed subtitles that match the narration audio,
    with proper line breaks and reading-speed optimized timing.
    """

    name = "caption_generator"

    # Average reading speed: ~150 words per minute, ~2.5 words per second
    WORDS_PER_SECOND = 2.5

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["script"]):
            raise ValueError("Script required before caption generation")

        api_keys = context["api_keys"]
        file_manager = context["file_manager"]

        self.logger.info("Generating captions from script")

        # Use LLM to create properly segmented captions with timing
        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        caption_prompt = f"""Convert this narration script into SRT subtitle format.

Rules:
- Maximum 2 lines per subtitle
- Maximum 42 characters per line
- Each subtitle should be 2-6 seconds long
- Time based on natural speech pace (~{self.WORDS_PER_SECOND} words/second)
- Break at natural pauses: sentence ends, commas, clause boundaries
- Number each subtitle sequentially starting at 1

Script:
{project.script}

Output ONLY valid SRT format, nothing else. Example:
1
00:00:00,000 --> 00:00:03,500
First line of subtitle
Second line if needed

2
00:00:03,800 --> 00:00:07,200
Next subtitle text here"""

        async def _generate():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=8192,
                messages=[{"role": "user", "content": caption_prompt}],
            )
            return response.content[0].text

        srt_content = await self.retry(_generate)

        # Clean up any markdown wrapping
        if "```" in srt_content:
            srt_content = srt_content.split("```")[1]
            if srt_content.startswith("srt"):
                srt_content = srt_content[3:]
            srt_content = srt_content.strip()

        # Save SRT file
        path = file_manager.save_text(
            project.channel_id, project.project_id, "captions.srt", srt_content
        )
        captions_path = str(path)

        project.captions_file = captions_path

        # Count subtitle entries
        subtitle_count = srt_content.count(" --> ")

        project.log_agent_action(self.name, "captions_generated", {
            "subtitle_count": subtitle_count,
            "file": captions_path,
        })

        await self.emit("captions.completed", {
            "project_id": project.project_id,
            "subtitle_count": subtitle_count,
        })

        self.logger.info(f"Generated {subtitle_count} subtitle entries: {captions_path}")
        return {"captions_file": captions_path, "subtitle_count": subtitle_count}
