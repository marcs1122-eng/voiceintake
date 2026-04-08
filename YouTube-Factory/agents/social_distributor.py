"""Social Distributor Agent - distributes content to TikTok and Instagram."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.base import BaseAgent
from core.state import VideoProject


class SocialDistributorAgent(BaseAgent):
    """Distributes short-form content to TikTok and Instagram Reels.

    Takes extracted shorts and uploads them with platform-optimized captions,
    hashtags, and metadata for maximum reach on each platform.
    """

    name = "social_distributor"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not project.shorts:
            self.logger.info("No shorts to distribute, skipping")
            return {"tiktok_urls": [], "instagram_urls": []}

        api_keys = context["api_keys"]
        channel_cfg = self.get_channel_config(project)
        dist_cfg = channel_cfg.get("distribution", {})
        seo_cfg = channel_cfg.get("seo", {})

        hashtags = seo_cfg.get("hashtags", [])
        tiktok_urls: list[str] = []
        instagram_urls: list[str] = []

        for short in project.shorts:
            caption = self._build_caption(
                title=short.get("title", ""),
                hook=short.get("hook_text", ""),
                hashtags=hashtags,
                youtube_url=project.youtube_url,
            )

            # Upload to TikTok
            if dist_cfg.get("tiktok"):
                tiktok_creds = api_keys.get("tiktok", {})
                if tiktok_creds.get("access_token"):
                    url = await self._upload_tiktok(
                        video_path=short["path"],
                        caption=caption,
                        credentials=tiktok_creds,
                    )
                    if url:
                        tiktok_urls.append(url)

            # Upload to Instagram Reels
            if dist_cfg.get("instagram_reels"):
                ig_creds = api_keys.get("instagram", {})
                if ig_creds.get("access_token"):
                    url = await self._upload_instagram_reel(
                        video_path=short["path"],
                        caption=caption,
                        credentials=ig_creds,
                    )
                    if url:
                        instagram_urls.append(url)

        project.tiktok_urls = tiktok_urls
        project.instagram_urls = instagram_urls

        project.log_agent_action(self.name, "social_distributed", {
            "tiktok_count": len(tiktok_urls),
            "instagram_count": len(instagram_urls),
        })

        await self.emit("social.distributed", {
            "project_id": project.project_id,
            "tiktok": tiktok_urls,
            "instagram": instagram_urls,
        })

        self.logger.info(
            f"Distributed: {len(tiktok_urls)} TikTok, {len(instagram_urls)} Instagram"
        )
        return {"tiktok_urls": tiktok_urls, "instagram_urls": instagram_urls}

    def _build_caption(
        self,
        title: str,
        hook: str,
        hashtags: list[str],
        youtube_url: str,
    ) -> str:
        """Build platform-optimized caption."""
        parts = []
        if hook:
            parts.append(hook)
        elif title:
            parts.append(title)

        if youtube_url:
            parts.append(f"\nFull video: {youtube_url}")

        if hashtags:
            parts.append("\n" + " ".join(hashtags[:10]))

        return "\n".join(parts)

    async def _upload_tiktok(
        self,
        video_path: str,
        caption: str,
        credentials: dict,
    ) -> str | None:
        """Upload video to TikTok using their API."""
        from utils.api_client import APIClient

        client = APIClient(
            base_url="https://open.tiktokapis.com/v2",
            api_key=credentials.get("access_token", ""),
            timeout=300.0,
        )

        try:
            # Step 1: Initialize upload
            init_result = await client.post(
                "/post/publish/inbox/video/init/",
                json={
                    "post_info": {
                        "title": caption[:150],
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "disable_duet": False,
                        "disable_comment": False,
                        "disable_stitch": False,
                    },
                    "source_info": {
                        "source": "FILE_UPLOAD",
                        "video_size": self._get_file_size(video_path),
                    },
                },
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )

            upload_url = init_result.get("data", {}).get("upload_url", "")
            publish_id = init_result.get("data", {}).get("publish_id", "")

            if not upload_url:
                self.logger.warning("TikTok upload init failed - no upload URL")
                return None

            # Step 2: Upload video file
            import httpx
            async with httpx.AsyncClient(timeout=300.0) as http:
                with open(video_path, "rb") as f:
                    resp = await http.put(
                        upload_url,
                        content=f.read(),
                        headers={"Content-Type": "video/mp4"},
                    )
                    resp.raise_for_status()

            return f"https://www.tiktok.com/@/video/{publish_id}" if publish_id else None

        except Exception as e:
            self.logger.error(f"TikTok upload failed: {e}")
            return None
        finally:
            await client.close()

    async def _upload_instagram_reel(
        self,
        video_path: str,
        caption: str,
        credentials: dict,
    ) -> str | None:
        """Upload video as Instagram Reel via Graph API."""
        from utils.api_client import APIClient

        account_id = credentials.get("business_account_id", "")
        access_token = credentials.get("access_token", "")

        client = APIClient(
            base_url="https://graph.facebook.com/v18.0",
            timeout=300.0,
        )

        try:
            # Step 1: Create media container
            result = await client.post(
                f"/{account_id}/media",
                params={
                    "media_type": "REELS",
                    "video_url": video_path,  # Must be publicly accessible URL
                    "caption": caption,
                    "access_token": access_token,
                },
            )

            container_id = result.get("id", "")
            if not container_id:
                return None

            # Step 2: Wait for processing then publish
            await asyncio.sleep(10)  # Instagram needs time to process

            publish_result = await client.post(
                f"/{account_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": access_token,
                },
            )

            media_id = publish_result.get("id", "")
            return f"https://www.instagram.com/reel/{media_id}/" if media_id else None

        except Exception as e:
            self.logger.error(f"Instagram upload failed: {e}")
            return None
        finally:
            await client.close()

    def _get_file_size(self, path: str) -> int:
        from pathlib import Path
        return Path(path).stat().st_size
