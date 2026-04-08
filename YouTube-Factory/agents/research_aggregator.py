"""Research Aggregator Agent - gathers and synthesizes source material for content."""

from __future__ import annotations

from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class ResearchAggregatorAgent(BaseAgent):
    """Aggregates research data from multiple sources to fuel script creation.

    Gathers information from configured sources (news, court records, trending
    topics, etc.) based on channel niche, then synthesizes a research brief.
    """

    name = "research_aggregator"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        channel_cfg = self.get_channel_config(project)
        api_keys = context["api_keys"]
        research_cfg = channel_cfg.get("research", {})
        sources = research_cfg.get("sources", [])
        niche = channel_cfg.get("niche", "general")

        self.logger.info(f"Researching topic '{project.topic}' for niche '{niche}'")

        # Build the research prompt based on channel type
        source_instructions = "\n".join(f"- {src}" for src in sources)
        sensitivity = research_cfg.get("sensitivity_filter", "medium")
        avoid = research_cfg.get("avoid_topics", [])
        avoid_str = ", ".join(avoid) if avoid else "none"

        research_prompt = f"""You are a research assistant for a {niche} content channel.

Topic to research: {project.topic}

Research this topic thoroughly and provide a structured brief with:

1. **Key Facts & Timeline**: Chronological events, dates, names, locations
2. **Background Context**: Historical context, related events, significance
3. **Compelling Angles**: Unique perspectives, lesser-known details, emotional hooks
4. **Quotes & Sources**: Notable quotes, witness statements, expert opinions
5. **Visual Description Ideas**: Key scenes, locations, or moments to visualize
6. **Content Warnings**: Any sensitive material that needs careful handling

Research sources to consider: {source_instructions}
Sensitivity level: {sensitivity}
Topics to avoid: {avoid_str}

Provide factual, well-organized research that a scriptwriter can use directly.
Format the output as structured sections with clear headers."""

        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        async def _call_llm():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=4096,
                messages=[{"role": "user", "content": research_prompt}],
            )
            return response.content[0].text

        research_text = await self.retry(_call_llm)

        # Parse into structured data
        research_data = {
            "topic": project.topic,
            "niche": niche,
            "raw_brief": research_text,
            "sources_consulted": sources,
            "sensitivity_level": sensitivity,
        }

        project.research_data = research_data
        project.log_agent_action(self.name, "research_completed", {
            "topic": project.topic,
            "brief_length": len(research_text),
        })

        await self.emit("research.completed", {
            "project_id": project.project_id,
            "brief_length": len(research_text),
        })

        self.logger.info(f"Research complete: {len(research_text)} chars")
        return research_data
