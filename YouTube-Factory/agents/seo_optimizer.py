"""SEO Optimizer Agent - optimizes metadata for maximum discoverability."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class SEOOptimizerAgent(BaseAgent):
    """Optimizes video titles, descriptions, and tags for YouTube SEO.

    Analyzes the content, channel niche, and trending keywords to generate
    optimized metadata that maximizes search visibility and CTR.
    """

    name = "seo_optimizer"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["title", "script"]):
            raise ValueError("Title and script required before SEO optimization")

        api_keys = context["api_keys"]
        channel_cfg = self.get_channel_config(project)
        seo_cfg = channel_cfg.get("seo", {})

        primary_keywords = seo_cfg.get("primary_keywords", [])
        hashtags = seo_cfg.get("hashtags", [])
        category = seo_cfg.get("category", "Entertainment")
        language = seo_cfg.get("default_language", "en")

        self.logger.info(f"Optimizing SEO for '{project.title}'")

        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        # Truncate script for context (keep it under token limits)
        script_excerpt = project.script[:3000]

        seo_prompt = f"""You are a YouTube SEO expert. Optimize the metadata for this video:

Original title: {project.title}
Channel: {channel_cfg.get('name', '')}
Niche: {channel_cfg.get('niche', '')}
Category: {category}
Language: {language}

Primary keywords for this channel: {', '.join(primary_keywords)}
Channel hashtags: {', '.join(hashtags)}

Script excerpt:
{script_excerpt}

Generate optimized metadata:

1. **SEO Title** (max 70 chars): Include primary keyword near the start.
   Make it curiosity-driven and clickable. Use power words.

2. **Description** (2000+ chars):
   - First 150 chars are critical (shown in search)
   - Include primary keywords naturally in first 2 sentences
   - Add timestamps/chapters if applicable
   - Include relevant links placeholder
   - End with hashtags
   - Include a call to action

3. **Tags** (30 tags): Mix of:
   - Exact match keywords
   - Long-tail variations
   - Related topics
   - Channel-specific tags
   - Trending related terms

Output as JSON:
{{
  "title": "SEO optimized title",
  "description": "Full description with timestamps and CTA",
  "tags": ["tag1", "tag2", ...],
  "category": "{category}",
  "default_language": "{language}"
}}"""

        async def _optimize():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=4096,
                messages=[{"role": "user", "content": seo_prompt}],
            )
            return response.content[0].text

        raw = await self.retry(_optimize)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        seo_data = json.loads(raw.strip())

        project.seo_title = seo_data.get("title", project.title)
        project.seo_description = seo_data.get("description", "")
        project.seo_tags = seo_data.get("tags", [])

        project.log_agent_action(self.name, "seo_optimized", {
            "title": project.seo_title,
            "tags_count": len(project.seo_tags),
            "description_length": len(project.seo_description),
        })

        await self.emit("seo.completed", {
            "project_id": project.project_id,
            "title": project.seo_title,
        })

        self.logger.info(
            f"SEO optimized: '{project.seo_title}' with {len(project.seo_tags)} tags"
        )
        return seo_data
