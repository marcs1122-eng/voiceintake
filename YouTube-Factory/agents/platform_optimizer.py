"""Platform Optimization Specialist Agent - tailors content per platform."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class PlatformOptimizerAgent(BaseAgent):
    """Optimizes content strategy for each distribution platform.

    Analyzes past performance data and platform-specific best practices to
    recommend adjustments to content format, posting times, hashtags, and
    engagement strategies for YouTube, TikTok, and Instagram.
    """

    name = "platform_optimizer"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        api_keys = context["api_keys"]
        channel_cfg = self.get_channel_config(project)
        file_manager = context["file_manager"]

        self.logger.info(f"Running platform optimization for '{project.channel_id}'")

        # Load historical analytics for this channel
        from pathlib import Path
        history_path = (
            Path(file_manager.base_dir) / project.channel_id / "analytics_history.jsonl"
        )

        history_data = []
        if history_path.exists():
            with open(history_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        history_data.append(json.loads(line))

        # Take last 20 entries for analysis
        recent_history = history_data[-20:] if history_data else []

        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        optimization_prompt = f"""You are a social media platform optimization specialist.

Channel: {channel_cfg.get('name', '')}
Niche: {channel_cfg.get('niche', '')}
Current topic: {project.topic}

Distribution platforms:
- YouTube (long-form + Shorts)
- TikTok
- Instagram Reels

Recent performance data ({len(recent_history)} videos):
{json.dumps(recent_history[-5:], indent=2) if recent_history else "No historical data yet"}

Current channel schedule:
{json.dumps(channel_cfg.get('schedule', {}), indent=2)}

Analyze and provide platform-specific optimization recommendations:

1. **YouTube Long-Form**: Optimal upload time, title patterns that work,
   retention strategies, end screen placement
2. **YouTube Shorts**: Best performing formats, hook styles, optimal length
3. **TikTok**: Trending sounds/formats to leverage, caption style,
   optimal posting frequency
4. **Instagram Reels**: Cover image strategy, hashtag groups,
   collaboration opportunities

Also provide:
- Content gap analysis (topics competitors cover that we don't)
- Suggested A/B tests for thumbnails and titles
- Cross-platform promotion strategy

Output as JSON:
{{
  "youtube_long_form": {{
    "optimal_upload_time": "HH:MM",
    "title_recommendations": ["..."],
    "retention_tips": ["..."]
  }},
  "youtube_shorts": {{
    "optimal_length_seconds": 45,
    "hook_styles": ["..."],
    "format_recommendations": ["..."]
  }},
  "tiktok": {{
    "posting_frequency": "daily",
    "caption_style": "...",
    "trending_formats": ["..."]
  }},
  "instagram": {{
    "hashtag_groups": [["..."]],
    "cover_strategy": "...",
    "posting_tips": ["..."]
  }},
  "ab_tests": [
    {{"test": "...", "variant_a": "...", "variant_b": "..."}}
  ],
  "cross_promotion": ["..."]
}}"""

        async def _analyze():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=4096,
                messages=[{"role": "user", "content": optimization_prompt}],
            )
            return response.content[0].text

        raw = await self.retry(_analyze)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        recommendations = json.loads(raw.strip())

        # Save recommendations
        file_manager.save_text(
            project.channel_id,
            project.project_id,
            "platform_optimization.json",
            json.dumps(recommendations, indent=2),
        )

        project.log_agent_action(self.name, "platform_optimized", {
            "platforms_analyzed": ["youtube", "tiktok", "instagram"],
            "ab_tests_suggested": len(recommendations.get("ab_tests", [])),
        })

        await self.emit("platform.optimized", {
            "project_id": project.project_id,
        })

        self.logger.info("Platform optimization complete")
        return recommendations
