"""YouTube Uploader Agent - handles video upload to YouTube via API."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.base import BaseAgent
from core.state import VideoProject


class YouTubeUploaderAgent(BaseAgent):
    """Uploads videos to YouTube with optimized metadata.

    Handles the full upload flow: authentication, video upload, metadata
    setting (title, description, tags, thumbnail), and publish scheduling.
    """

    name = "youtube_uploader"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["composed_video", "seo_title"]):
            raise ValueError("Composed video and SEO data required before upload")

        api_keys = context["api_keys"]
        channel_cfg = self.get_channel_config(project)
        seo_cfg = channel_cfg.get("seo", {})

        yt_creds = api_keys.get("youtube", {})
        if not yt_creds.get("client_id"):
            raise ValueError("YouTube API credentials not configured")

        self.logger.info(f"Uploading to YouTube: '{project.seo_title}'")

        # Build YouTube API upload request
        video_metadata = {
            "snippet": {
                "title": project.seo_title,
                "description": project.seo_description,
                "tags": project.seo_tags[:500],  # YouTube tag limit
                "categoryId": self._get_category_id(seo_cfg.get("category", "Entertainment")),
                "defaultLanguage": seo_cfg.get("default_language", "en"),
            },
            "status": {
                "privacyStatus": "private",  # Start private, schedule later
                "selfDeclaredMadeForKids": False,
                "embeddable": True,
                "publicStatsViewable": True,
            },
        }

        # Set scheduled publish time if configured
        if project.scheduled_publish_time:
            video_metadata["status"]["privacyStatus"] = "private"
            video_metadata["status"]["publishAt"] = project.scheduled_publish_time

        # Upload via YouTube Data API v3
        upload_result = await self._upload_video(
            video_path=project.composed_video,
            metadata=video_metadata,
            thumbnail_path=project.thumbnail_path,
            credentials=yt_creds,
        )

        video_id = upload_result.get("id", "")
        youtube_url = f"https://youtube.com/watch?v={video_id}" if video_id else ""

        project.youtube_url = youtube_url

        # Upload shorts as separate videos
        shorts_urls = []
        for short in project.shorts:
            short_meta = {
                "snippet": {
                    "title": f"{short.get('title', '')} #Shorts",
                    "description": (
                        f"{short.get('hook_text', '')}\n\n"
                        f"Full video: {youtube_url}\n\n"
                        f"{' '.join(channel_cfg.get('seo', {}).get('hashtags', []))}"
                    ),
                    "tags": project.seo_tags[:20],
                    "categoryId": self._get_category_id(seo_cfg.get("category", "Entertainment")),
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            }
            short_result = await self._upload_video(
                video_path=short["path"],
                metadata=short_meta,
                credentials=yt_creds,
            )
            short_id = short_result.get("id", "")
            if short_id:
                shorts_urls.append(f"https://youtube.com/shorts/{short_id}")

        project.log_agent_action(self.name, "youtube_uploaded", {
            "video_url": youtube_url,
            "shorts_uploaded": len(shorts_urls),
        })

        await self.emit("youtube.uploaded", {
            "project_id": project.project_id,
            "url": youtube_url,
            "shorts": shorts_urls,
        })

        self.logger.info(f"YouTube upload complete: {youtube_url}")
        return {"youtube_url": youtube_url, "shorts_urls": shorts_urls}

    async def _upload_video(
        self,
        video_path: str,
        metadata: dict,
        credentials: dict,
        thumbnail_path: str | None = None,
    ) -> dict[str, Any]:
        """Upload a video to YouTube using the Data API v3."""
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = Credentials(
            token=None,
            refresh_token=credentials.get("refresh_token", ""),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=credentials.get("client_id", ""),
            client_secret=credentials.get("client_secret", ""),
        )

        youtube = build("youtube", "v3", credentials=creds)

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=10 * 1024 * 1024,  # 10MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=metadata,
            media_body=media,
        )

        # Resumable upload with progress tracking
        response = None
        while response is None:
            status, response = await asyncio.to_thread(request.next_chunk)
            if status:
                self.logger.debug(f"Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id", "")

        # Set thumbnail if provided
        if thumbnail_path and video_id:
            thumb_media = MediaFileUpload(thumbnail_path, mimetype="image/png")
            await asyncio.to_thread(
                youtube.thumbnails().set(videoId=video_id, media_body=thumb_media).execute
            )

        return response

    def _get_category_id(self, category_name: str) -> str:
        """Map category name to YouTube category ID."""
        categories = {
            "Entertainment": "24",
            "Comedy": "23",
            "Education": "27",
            "Science & Technology": "28",
            "News & Politics": "25",
            "People & Blogs": "22",
            "Film & Animation": "1",
            "Music": "10",
            "Gaming": "20",
            "Howto & Style": "26",
        }
        return categories.get(category_name, "24")
