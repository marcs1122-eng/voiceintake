"""Image Prompt Engineer Agent - crafts optimized prompts for image generation."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class ImagePromptEngineerAgent(BaseAgent):
    """Translates script visual directions into optimized image generation prompts.

    Takes the visual directions from each script section and engineers detailed,
    model-specific prompts that produce consistent, high-quality imagery matching
    the channel's visual style.
    """

    name = "image_prompt_engineer"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["script_sections"]):
            raise ValueError("Script sections required before image prompt engineering")

        channel_cfg = self.get_channel_config(project)
        api_keys = context["api_keys"]
        visual_cfg = channel_cfg.get("visuals", {})
        style = visual_cfg.get("style", "cinematic")
        prefix = visual_cfg.get("image_prompt_prefix", "")
        negative = visual_cfg.get("negative_prompts", "")
        palette = visual_cfg.get("color_palette", [])

        palette_str = ", ".join(palette) if palette else "default"

        # Collect visual directions from all sections
        visual_directions = []
        for i, section in enumerate(project.script_sections):
            visual_directions.append({
                "section_index": i,
                "section_title": section.get("title", f"Section {i}"),
                "directions": section.get("visual_directions", ""),
                "pacing": section.get("pacing", "normal"),
            })

        prompt_engineering_request = f"""You are an expert image prompt engineer specializing in AI image generation.

Channel visual style: {style}
Color palette: {palette_str}
Standard prefix for all prompts: "{prefix}"
Negative prompts to always include: "{negative}"

For each visual direction below, create 1-2 detailed image generation prompts optimized
for the Higgsfield/Nano Banana Pro model. Each prompt should:

1. Start with the channel's standard prefix
2. Include specific composition details (camera angle, framing, lighting)
3. Specify mood, atmosphere, and color grading matching the palette
4. Include quality boosters (8k, detailed, professional, etc.)
5. Maintain visual consistency across all prompts (same style universe)
6. Be 50-120 words for optimal generation quality

Visual directions by section:
{json.dumps(visual_directions, indent=2)}

Output as JSON array:
[
  {{
    "section_index": 0,
    "prompts": [
      {{
        "prompt": "full positive prompt text",
        "negative_prompt": "negative prompt text",
        "aspect_ratio": "16:9",
        "style_preset": "cinematic"
      }}
    ]
  }}
]"""

        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        async def _call_llm():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt_engineering_request}],
            )
            return response.content[0].text

        raw = await self.retry(_call_llm)

        # Parse JSON
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        prompt_sets = json.loads(raw.strip())

        # Flatten all prompts into a single list for the image generator
        all_prompts = []
        for section_prompts in prompt_sets:
            for p in section_prompts.get("prompts", []):
                all_prompts.append(p["prompt"])

        project.image_prompts = all_prompts

        project.log_agent_action(self.name, "prompts_engineered", {
            "prompt_count": len(all_prompts),
        })

        await self.emit("image_prompts.completed", {
            "project_id": project.project_id,
            "prompt_count": len(all_prompts),
        })

        self.logger.info(f"Engineered {len(all_prompts)} image prompts")
        return {"prompt_sets": prompt_sets, "flat_prompts": all_prompts}
