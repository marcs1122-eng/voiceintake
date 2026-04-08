"""Analytics Tracker Agent - monitors video performance metrics."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.state import VideoProject


class AnalyticsTrackerAgent(BaseAgent):
    """Tracks and reports on video performance analytics.

    Monitors views, engagement, CTR, retention, and other metrics across
    YouTube, TikTok, and Instagram. Stores historical data for trend analysis.
    """

    name = "analytics_tracker"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        api_keys = context["api_keys"]
        file_manager = context["file_manager"]

        self.logger.info(f"Tracking analytics for project {project.project_id}")

        metrics: dict[str, Any] = {
            "project_id": project.project_id,
            "channel_id": project.channel_id,
            "title": project.seo_title or project.title,
            "tracked_at": datetime.utcnow().isoformat(),
            "platforms": {},
        }

        # YouTube Analytics
        if project.youtube_url:
            yt_metrics = await self._fetch_youtube_analytics(
                video_url=project.youtube_url,
                credentials=api_keys.get("youtube", {}),
            )
            metrics["platforms"]["youtube"] = yt_metrics

        # TikTok Analytics
        if project.tiktok_urls:
            tt_metrics = await self._fetch_tiktok_analytics(
                urls=project.tiktok_urls,
                credentials=api_keys.get("tiktok", {}),
            )
            metrics["platforms"]["tiktok"] = tt_metrics

        # Instagram Analytics
        if project.instagram_urls:
            ig_metrics = await self._fetch_instagram_analytics(
                urls=project.instagram_urls,
                credentials=api_keys.get("instagram", {}),
            )
            metrics["platforms"]["instagram"] = ig_metrics

        # Calculate aggregate scores
        metrics["aggregate"] = self._calculate_aggregate(metrics["platforms"])

        # Save analytics to file
        analytics_dir = file_manager.project_dir(project.channel_id, project.project_id)
        analytics_path = analytics_dir / "analytics.json"
        with open(analytics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        # Append to channel-level analytics history
        history_path = Path(file_manager.base_dir) / project.channel_id / "analytics_history.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        with open(history_path, "a") as f:
            f.write(json.dumps(metrics) + "\n")

        project.quality_score = metrics["aggregate"].get("overall_score", 0.0)

        project.log_agent_action(self.name, "analytics_tracked", {
            "platforms": list(metrics["platforms"].keys()),
            "overall_score": project.quality_score,
        })

        await self.emit("analytics.tracked", {
            "project_id": project.project_id,
            "score": project.quality_score,
        })

        self.logger.info(f"Analytics tracked. Overall score: {project.quality_score:.2f}")
        return metrics

    async def _fetch_youtube_analytics(
        self, video_url: str, credentials: dict
    ) -> dict[str, Any]:
        """Fetch YouTube analytics for a video."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            import asyncio

            video_id = video_url.split("v=")[-1].split("&")[0]

            creds = Credentials(
                token=None,
                refresh_token=credentials.get("refresh_token", ""),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=credentials.get("client_id", ""),
                client_secret=credentials.get("client_secret", ""),
            )

            youtube = build("youtube", "v3", credentials=creds)

            result = await asyncio.to_thread(
                youtube.videos().list(
                    part="statistics,contentDetails",
                    id=video_id,
                ).execute
            )

            items = result.get("items", [])
            if not items:
                return {"error": "Video not found"}

            stats = items[0].get("statistics", {})
            return {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "favorites": int(stats.get("favoriteCount", 0)),
            }

        except Exception as e:
            self.logger.warning(f"YouTube analytics fetch failed: {e}")
            return {"error": str(e)}

    async def _fetch_tiktok_analytics(
        self, urls: list[str], credentials: dict
    ) -> dict[str, Any]:
        """Fetch TikTok analytics."""
        from utils.api_client import APIClient

        client = APIClient(
            base_url="https://open.tiktokapis.com/v2",
            api_key=credentials.get("access_token", ""),
        )

        total = {"views": 0, "likes": 0, "comments": 0, "shares": 0, "videos": len(urls)}

        try:
            for url in urls:
                video_id = url.rstrip("/").split("/")[-1]
                try:
                    result = await client.post(
                        "/video/query/",
                        json={"filters": {"video_ids": [video_id]}},
                        headers={
                            "Authorization": f"Bearer {credentials.get('access_token', '')}"
                        },
                    )
                    data = result.get("data", {}).get("videos", [{}])[0]
                    total["views"] += data.get("view_count", 0)
                    total["likes"] += data.get("like_count", 0)
                    total["comments"] += data.get("comment_count", 0)
                    total["shares"] += data.get("share_count", 0)
                except Exception:
                    pass
        finally:
            await client.close()

        return total

    async def _fetch_instagram_analytics(
        self, urls: list[str], credentials: dict
    ) -> dict[str, Any]:
        """Fetch Instagram analytics."""
        from utils.api_client import APIClient

        client = APIClient(base_url="https://graph.facebook.com/v18.0")
        total = {"views": 0, "likes": 0, "comments": 0, "saves": 0, "reels": len(urls)}

        try:
            for url in urls:
                media_id = url.rstrip("/").split("/")[-1]
                try:
                    result = await client.get(
                        f"/{media_id}",
                        params={
                            "fields": "like_count,comments_count,insights.metric(impressions,saved)",
                            "access_token": credentials.get("access_token", ""),
                        },
                    )
                    total["likes"] += result.get("like_count", 0)
                    total["comments"] += result.get("comments_count", 0)
                except Exception:
                    pass
        finally:
            await client.close()

        return total

    def _calculate_aggregate(self, platforms: dict[str, Any]) -> dict[str, Any]:
        """Calculate aggregate performance score across platforms."""
        total_views = 0
        total_engagement = 0

        for platform, data in platforms.items():
            if isinstance(data, dict) and "error" not in data:
                views = data.get("views", 0)
                likes = data.get("likes", 0)
                comments = data.get("comments", 0)
                total_views += views
                total_engagement += likes + comments

        engagement_rate = (total_engagement / total_views * 100) if total_views > 0 else 0

        # Score: 0-1 based on engagement rate (5%+ is excellent)
        score = min(engagement_rate / 5.0, 1.0)

        return {
            "total_views": total_views,
            "total_engagement": total_engagement,
            "engagement_rate": round(engagement_rate, 2),
            "overall_score": round(score, 3),
        }
