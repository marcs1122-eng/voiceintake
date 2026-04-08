"""Master Orchestrator Agent - coordinates the entire video production pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from agents.base import BaseAgent
from agents.research_aggregator import ResearchAggregatorAgent
from agents.script_generator import ScriptGeneratorAgent
from agents.image_prompt_engineer import ImagePromptEngineerAgent
from agents.image_generator import ImageGeneratorAgent
from agents.video_composer import VideoComposerAgent
from agents.voice_narrator import VoiceNarratorAgent
from agents.caption_generator import CaptionGeneratorAgent
from agents.shorts_extractor import ShortsExtractorAgent
from agents.thumbnail_generator import ThumbnailGeneratorAgent
from agents.seo_optimizer import SEOOptimizerAgent
from agents.youtube_uploader import YouTubeUploaderAgent
from agents.social_distributor import SocialDistributorAgent
from agents.content_scheduler import ContentSchedulerAgent
from agents.analytics_tracker import AnalyticsTrackerAgent
from agents.platform_optimizer import PlatformOptimizerAgent
from agents.competitive_analyzer import CompetitiveAnalyzerAgent

from core.pipeline import Pipeline, PipelineStage, StageResult
from core.state import VideoProject, VideoStatus, ProjectState
from core.events import EventBus, Event
from utils.file_manager import FileManager

logger = logging.getLogger(__name__)


class MasterOrchestrator(BaseAgent):
    """Central orchestrator that coordinates all agents through the production pipeline.

    The orchestrator:
    1. Reads channel configs and determines what content to produce
    2. Creates video projects for each channel
    3. Runs projects through the full pipeline (research -> publish)
    4. Handles errors, retries, and reporting
    5. Manages concurrent production across channels

    Usage:
        orchestrator = MasterOrchestrator(config, event_bus)
        await orchestrator.produce(channel_id="dark_verdict", topic="The Zodiac Killer")
        # or produce for all channels:
        await orchestrator.produce_all(topics={"dark_verdict": "The Zodiac", ...})
    """

    name = "master_orchestrator"

    def __init__(self, config: dict[str, Any], event_bus: EventBus) -> None:
        super().__init__(config, event_bus)
        self.state = ProjectState()
        self.file_manager = FileManager(
            config.get("defaults", config).get("output_dir", "./output")
        )
        self._agents: dict[str, BaseAgent] = {}
        self._pipeline: Pipeline | None = None
        self._init_agents()

    def _init_agents(self) -> None:
        """Initialize all production agents."""
        agent_classes = [
            ResearchAggregatorAgent,
            ScriptGeneratorAgent,
            ImagePromptEngineerAgent,
            ImageGeneratorAgent,
            VideoComposerAgent,
            VoiceNarratorAgent,
            CaptionGeneratorAgent,
            ShortsExtractorAgent,
            ThumbnailGeneratorAgent,
            SEOOptimizerAgent,
            ContentSchedulerAgent,
            YouTubeUploaderAgent,
            SocialDistributorAgent,
            AnalyticsTrackerAgent,
            PlatformOptimizerAgent,
            CompetitiveAnalyzerAgent,
        ]

        for cls in agent_classes:
            agent = cls(config=self.config, event_bus=self.event_bus)
            self._agents[agent.name] = agent

        logger.info(f"Initialized {len(self._agents)} agents")

    def _build_pipeline(self) -> Pipeline:
        """Build the production pipeline with all stages."""
        pipeline = Pipeline(self.event_bus)

        def _make_stage(agent_name: str, status: VideoStatus, depends: list[str] | None = None, required: bool = True):
            agent = self._agents[agent_name]

            async def execute(project: VideoProject, context: dict[str, Any]) -> StageResult:
                try:
                    await agent.process(project, context)
                    return StageResult.SUCCESS
                except Exception as e:
                    logger.error(f"Stage '{agent_name}' failed: {e}", exc_info=True)
                    project.add_error(f"{agent_name}: {str(e)}")
                    return StageResult.FAILED

            return PipelineStage(
                name=agent_name,
                agent_name=agent_name,
                status_on_start=status,
                execute=execute,
                required=required,
                depends_on=depends or [],
            )

        # ── Stage 1: Research & Analysis (parallel-capable) ──
        pipeline.add_stage(_make_stage(
            "competitive_analyzer", VideoStatus.RESEARCHING,
            required=False,
        ))
        pipeline.add_stage(_make_stage(
            "research_aggregator", VideoStatus.RESEARCHING,
        ))

        # ── Stage 2: Script Generation ──
        pipeline.add_stage(_make_stage(
            "script_generator", VideoStatus.SCRIPTING,
            depends=["research_aggregator"],
        ))

        # ── Stage 3: Visual Preparation ──
        pipeline.add_stage(_make_stage(
            "image_prompt_engineer", VideoStatus.GENERATING_IMAGES,
            depends=["script_generator"],
        ))
        pipeline.add_stage(_make_stage(
            "image_generator", VideoStatus.GENERATING_IMAGES,
            depends=["image_prompt_engineer"],
        ))

        # ── Stage 4: Audio ──
        pipeline.add_stage(_make_stage(
            "voice_narrator", VideoStatus.NARRATING,
            depends=["script_generator"],
        ))

        # ── Stage 5: Video Composition ──
        pipeline.add_stage(_make_stage(
            "video_composer", VideoStatus.COMPOSING_VIDEO,
            depends=["image_generator", "voice_narrator"],
        ))

        # ── Stage 6: Post-Production (can run in parallel) ──
        pipeline.add_stage(_make_stage(
            "caption_generator", VideoStatus.CAPTIONING,
            depends=["script_generator"],
        ))
        pipeline.add_stage(_make_stage(
            "shorts_extractor", VideoStatus.EXTRACTING_SHORTS,
            depends=["video_composer"],
        ))
        pipeline.add_stage(_make_stage(
            "thumbnail_generator", VideoStatus.GENERATING_THUMBNAIL,
            depends=["script_generator"],
        ))

        # ── Stage 7: Optimization ──
        pipeline.add_stage(_make_stage(
            "seo_optimizer", VideoStatus.OPTIMIZING_SEO,
            depends=["script_generator"],
        ))
        pipeline.add_stage(_make_stage(
            "platform_optimizer", VideoStatus.OPTIMIZING_SEO,
            depends=["script_generator"],
            required=False,
        ))
        pipeline.add_stage(_make_stage(
            "content_scheduler", VideoStatus.OPTIMIZING_SEO,
            depends=["seo_optimizer"],
        ))

        # ── Stage 8: Publishing ──
        pipeline.add_stage(_make_stage(
            "youtube_uploader", VideoStatus.UPLOADING,
            depends=["video_composer", "seo_optimizer", "thumbnail_generator", "content_scheduler"],
        ))
        pipeline.add_stage(_make_stage(
            "social_distributor", VideoStatus.UPLOADING,
            depends=["shorts_extractor"],
            required=False,
        ))

        # ── Stage 9: Post-Publish Analytics ──
        pipeline.add_stage(_make_stage(
            "analytics_tracker", VideoStatus.PUBLISHED,
            depends=["youtube_uploader"],
            required=False,
        ))

        return pipeline

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        """Process a single video project through the full pipeline."""
        return await self.produce(
            channel_id=project.channel_id,
            topic=project.topic,
            api_keys=context.get("api_keys", {}),
        )

    async def produce(
        self,
        channel_id: str,
        topic: str,
        api_keys: dict[str, Any] | None = None,
        auto_publish: bool = False,
    ) -> dict[str, Any]:
        """Produce a single video for a channel.

        Args:
            channel_id: Which channel to produce for (must be in channels.yaml).
            topic: The topic/subject for the video.
            api_keys: API key configuration dict.
            auto_publish: If True, publish immediately. If False, stop at ready_for_review.

        Returns:
            Dict with project state and results.
        """
        # Validate channel exists
        channels = self.config.get("channels", {})
        if channel_id not in channels:
            available = list(channels.keys())
            raise ValueError(
                f"Unknown channel '{channel_id}'. Available: {available}"
            )

        logger.info(f"=== Starting production: [{channel_id}] '{topic}' ===")

        # Create project
        project = self.state.create_project(channel_id, topic)

        # Build context shared across all agents
        context: dict[str, Any] = {
            "api_keys": api_keys or {},
            "file_manager": self.file_manager,
            "channels": channels,
            "auto_publish": auto_publish,
            "scheduled_times": set(),
        }

        # Build and run pipeline
        pipeline = self._build_pipeline()

        await self.event_bus.emit(Event(
            name="production.started",
            source=self.name,
            data={"project_id": project.project_id, "channel": channel_id, "topic": topic},
        ))

        success = await pipeline.run(project, context)

        if success:
            project.update_status(VideoStatus.PUBLISHED)
            self.state.complete_project(project.project_id)
            logger.info(f"=== Production COMPLETE: [{channel_id}] '{topic}' ===")
        else:
            project.update_status(VideoStatus.FAILED)
            logger.error(
                f"=== Production FAILED: [{channel_id}] '{topic}' ===\n"
                f"Errors: {project.errors}"
            )

        # Save final project state
        output_dir = self.file_manager.project_dir(channel_id, project.project_id)
        project.save(output_dir)

        await self.event_bus.emit(Event(
            name="production.finished",
            source=self.name,
            data={
                "project_id": project.project_id,
                "success": success,
                "youtube_url": project.youtube_url,
            },
        ))

        return project.to_dict()

    async def produce_all(
        self,
        topics: dict[str, str],
        api_keys: dict[str, Any] | None = None,
        max_concurrent: int = 2,
    ) -> list[dict[str, Any]]:
        """Produce videos for multiple channels concurrently.

        Args:
            topics: Mapping of channel_id -> topic.
            api_keys: API key configuration.
            max_concurrent: Max channels to process simultaneously.

        Returns:
            List of project result dicts.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []

        async def _produce_with_limit(channel_id: str, topic: str):
            async with semaphore:
                return await self.produce(channel_id, topic, api_keys)

        tasks = [
            _produce_with_limit(cid, topic)
            for cid, topic in topics.items()
        ]

        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(completed):
            if isinstance(result, Exception):
                channel_id = list(topics.keys())[i]
                logger.error(f"Channel '{channel_id}' production failed: {result}")
                results.append({"channel_id": channel_id, "error": str(result)})
            else:
                results.append(result)

        return results

    async def suggest_topics(
        self,
        channel_id: str,
        count: int = 5,
        api_keys: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Use the competitive analyzer to suggest topics for a channel.

        Returns list of {"topic": "...", "angle": "...", "demand": "..."} dicts.
        """
        channels = self.config.get("channels", {})
        if channel_id not in channels:
            raise ValueError(f"Unknown channel: {channel_id}")

        # Create a lightweight project just for analysis
        project = VideoProject(channel_id=channel_id, topic="topic_discovery")
        context = {
            "api_keys": api_keys or {},
            "file_manager": self.file_manager,
            "channels": channels,
        }

        analyzer = self._agents["competitive_analyzer"]
        result = await analyzer.process(project, context)

        suggestions = result.get("topic_suggestions", [])[:count]
        logger.info(f"Suggested {len(suggestions)} topics for '{channel_id}'")
        return suggestions
