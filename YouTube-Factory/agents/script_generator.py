"""Script Generator Agent - creates video scripts from research data."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class ScriptGeneratorAgent(BaseAgent):
    """Generates full video scripts based on research and channel style.

    Produces structured scripts with sections, narration text, visual cues,
    and timing markers tailored to the channel's tone and format.
    """

    name = "script_generator"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["research_data"]):
            raise ValueError("Research data required before script generation")

        channel_cfg = self.get_channel_config(project)
        api_keys = context["api_keys"]
        content_cfg = channel_cfg.get("content", {}).get("long_form", {})
        tone = channel_cfg.get("tone", "neutral")
        target_duration = content_cfg.get("target_duration", 600)
        hook_seconds = content_cfg.get("intro_hook_seconds", 15)
        style = content_cfg.get("style", "narration")

        # Estimate word count from duration (~150 words per minute of narration)
        target_words = int((target_duration / 60) * 150)

        research_brief = project.research_data.get("raw_brief", "")

        script_prompt = f"""You are an expert scriptwriter for a {channel_cfg.get('niche', '')} YouTube channel.
Channel name: {channel_cfg.get('name', '')}
Tagline: {channel_cfg.get('tagline', '')}
Tone: {tone}
Style: {style}
Target duration: {target_duration} seconds (~{target_words} words of narration)

RESEARCH BRIEF:
{research_brief}

Write a complete video script with the following structure:

1. **HOOK** (first {hook_seconds} seconds): A gripping opening that stops the scroll.
   Start with the most dramatic or intriguing element.

2. **INTRO**: Brief channel intro and topic setup.

3. **BODY**: The main content, divided into 3-5 clear sections.
   Each section should have:
   - Section title
   - Narration text (what the voice-over says)
   - Visual directions (what the viewer should see on screen)
   - Pacing notes (fast, slow, dramatic pause, etc.)

4. **CLIMAX**: The most intense or revealing moment.

5. **CONCLUSION**: Wrap-up with a call to action (subscribe, comment).

Output as JSON with this structure:
{{
  "title": "Video title",
  "hook": "Opening narration text",
  "sections": [
    {{
      "title": "Section name",
      "narration": "Full narration text for this section",
      "visual_directions": "Description of visuals",
      "pacing": "fast|normal|slow|dramatic",
      "estimated_duration_seconds": 120
    }}
  ],
  "call_to_action": "Closing CTA text",
  "total_word_count": 1500
}}"""

        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        async def _call_llm():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=8192,
                messages=[{"role": "user", "content": script_prompt}],
            )
            return response.content[0].text

        raw_response = await self.retry(_call_llm)

        # Parse JSON from response (handle markdown code blocks)
        json_str = raw_response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        script_data = json.loads(json_str.strip())

        # Build full narration script
        full_narration = script_data.get("hook", "")
        sections = script_data.get("sections", [])
        for section in sections:
            full_narration += "\n\n" + section.get("narration", "")
        full_narration += "\n\n" + script_data.get("call_to_action", "")

        project.title = script_data.get("title", project.topic)
        project.script = full_narration.strip()
        project.script_sections = sections

        project.log_agent_action(self.name, "script_generated", {
            "title": project.title,
            "sections": len(sections),
            "word_count": len(full_narration.split()),
        })

        await self.emit("script.completed", {
            "project_id": project.project_id,
            "title": project.title,
        })

        self.logger.info(
            f"Script generated: '{project.title}' - {len(sections)} sections, "
            f"{len(full_narration.split())} words"
        )
        return script_data
