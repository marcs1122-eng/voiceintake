"""Competitive Analysis Agent - analyzes competitor channels and trends."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class CompetitiveAnalyzerAgent(BaseAgent):
    """Performs competitive analysis on similar channels in the niche.

    Identifies top performers, analyzes their content strategies, title patterns,
    posting schedules, and engagement metrics to inform content decisions.
    """

    name = "competitive_analyzer"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        api_keys = context["api_keys"]
        file_manager = context["file_manager"]
        channel_cfg = self.get_channel_config(project)

        niche = channel_cfg.get("niche", "general")
        channel_name = channel_cfg.get("name", "")
        keywords = channel_cfg.get("seo", {}).get("primary_keywords", [])

        self.logger.info(f"Running competitive analysis for niche '{niche}'")

        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        analysis_prompt = f"""You are a YouTube competitive intelligence analyst.

Our channel: {channel_name}
Niche: {niche}
Primary keywords: {', '.join(keywords)}
Current topic: {project.topic}

Perform a competitive analysis:

1. **Top Competitors**: Identify 5-10 channels in the {niche} niche that are
   most successful. For each, analyze:
   - Content style and format
   - Upload frequency
   - Title/thumbnail patterns
   - Engagement strategies
   - What makes them successful

2. **Content Gaps**: What topics or angles are underserved in this niche?
   What could our channel do differently?

3. **Trending Topics**: What's currently trending in {niche}?
   What topics are getting high search volume?

4. **Title & Thumbnail Patterns**: What title formulas and thumbnail
   styles get the highest CTR in this niche?

5. **Audience Insights**: Who watches {niche} content? Demographics,
   viewing habits, what they engage with most.

6. **Topic Suggestions**: Based on competitive gaps and trends,
   suggest 10 video topics that could perform well for our channel.

Output as JSON:
{{
  "competitors": [
    {{
      "name": "Channel Name",
      "estimated_subscribers": "1M+",
      "content_style": "...",
      "upload_frequency": "...",
      "strengths": ["..."],
      "weaknesses": ["..."]
    }}
  ],
  "content_gaps": ["..."],
  "trending_topics": ["..."],
  "title_formulas": ["..."],
  "thumbnail_patterns": ["..."],
  "audience_insights": {{
    "primary_demographics": "...",
    "viewing_habits": "...",
    "engagement_drivers": ["..."]
  }},
  "topic_suggestions": [
    {{
      "topic": "...",
      "angle": "...",
      "estimated_demand": "high|medium|low",
      "competition_level": "high|medium|low"
    }}
  ]
}}"""

        async def _analyze():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=8192,
                messages=[{"role": "user", "content": analysis_prompt}],
            )
            return response.content[0].text

        raw = await self.retry(_analyze)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        analysis = json.loads(raw.strip())

        # Save competitive analysis report
        file_manager.save_text(
            project.channel_id,
            project.project_id,
            "competitive_analysis.json",
            json.dumps(analysis, indent=2),
        )

        project.log_agent_action(self.name, "competitive_analysis_completed", {
            "competitors_analyzed": len(analysis.get("competitors", [])),
            "topics_suggested": len(analysis.get("topic_suggestions", [])),
        })

        await self.emit("competitive.analyzed", {
            "project_id": project.project_id,
            "competitors": len(analysis.get("competitors", [])),
        })

        self.logger.info(
            f"Competitive analysis complete: {len(analysis.get('competitors', []))} "
            f"competitors, {len(analysis.get('topic_suggestions', []))} topic suggestions"
        )
        return analysis
