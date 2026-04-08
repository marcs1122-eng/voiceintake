"""Video Composer Agent - composes final video using Kling AI."""

from __future__ import annotations

import asyncio
from typing import Any

from agents.base import BaseAgent
from core.state import VideoProject


class VideoComposerAgent(BaseAgent):
    """Composes video from generated images and audio using Kling AI.

    Takes generated scene images, animates them into video clips using Kling's
    image-to-video capability, then assembles the final video with narration
    and background music.
    """

    name = "video_composer"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["generated_images"]):
            raise ValueError("Generated images required before video composition")

        api_keys = context["api_keys"]
        file_manager = context["file_manager"]
        channel_cfg = self.get_channel_config(project)
        content_cfg = channel_cfg.get("content", {}).get("long_form", {})
        target_duration = content_cfg.get("target_duration", 600)

        kling_key = api_keys.get("kling", {}).get("api_key", "")
        kling_url = api_keys.get("kling", {}).get("base_url", "https://api.kling.ai/v1")

        self.logger.info(
            f"Composing video from {len(project.generated_images)} images "
            f"(target: {target_duration}s)"
        )

        # Step 1: Generate video clips from each image using Kling
        video_clips = []
        clip_duration = max(3, target_duration // max(len(project.generated_images), 1))

        for i, image_path in enumerate(project.generated_images):
            clip_path = await self._image_to_video(
                image_path=image_path,
                index=i,
                duration=clip_duration,
                api_key=kling_key,
                base_url=kling_url,
                project=project,
                file_manager=file_manager,
            )
            if clip_path:
                video_clips.append(clip_path)

        project.video_clips = video_clips

        # Step 2: Assemble final video with ffmpeg
        final_path = await self._assemble_video(
            clips=video_clips,
            narration=project.narration_audio,
            project=project,
            file_manager=file_manager,
        )

        project.composed_video = final_path

        project.log_agent_action(self.name, "video_composed", {
            "clips_count": len(video_clips),
            "final_video": final_path,
        })

        await self.emit("video.composed", {
            "project_id": project.project_id,
            "video_path": final_path,
        })

        self.logger.info(f"Video composed: {final_path}")
        return {"video_clips": video_clips, "composed_video": final_path}

    async def _image_to_video(
        self,
        image_path: str,
        index: int,
        duration: int,
        api_key: str,
        base_url: str,
        project: VideoProject,
        file_manager,
    ) -> str | None:
        """Convert a single image to a video clip using Kling AI."""
        from utils.api_client import APIClient
        import base64
        from pathlib import Path

        client = APIClient(base_url=base_url, api_key=api_key, timeout=300.0)

        try:
            # Read and encode image
            image_data = Path(image_path).read_bytes()
            b64_image = base64.b64encode(image_data).decode()

            # Get motion direction from script section pacing
            pacing = "normal"
            if index < len(project.script_sections):
                pacing = project.script_sections[index].get("pacing", "normal")

            motion_map = {
                "fast": "dynamic",
                "slow": "gentle_pan",
                "dramatic": "zoom_in",
                "normal": "subtle_motion",
            }

            # Kling image-to-video API
            result = await client.post("/videos/image-to-video", json={
                "image": b64_image,
                "duration": min(duration, 10),  # Kling max per clip
                "motion_type": motion_map.get(pacing, "subtle_motion"),
                "quality": "high",
                "output_format": "mp4",
            })

            video_url = result.get("video", {}).get("url", "")
            if not video_url:
                # Poll for completion if async
                task_id = result.get("task_id", "")
                if task_id:
                    video_url = await self._poll_kling_task(client, task_id)

            if not video_url:
                self.logger.warning(f"No video generated for clip {index}")
                return None

            # Download clip
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.get(video_url)
                resp.raise_for_status()
                video_data = resp.content

            filename = f"clip_{index:03d}.mp4"
            path = file_manager.save_bytes(
                project.channel_id, project.project_id, filename, video_data
            )
            return str(path)

        except Exception as e:
            self.logger.error(f"Clip {index} generation failed: {e}")
            project.add_error(f"Video clip {index} failed: {str(e)}")
            return None
        finally:
            await client.close()

    async def _poll_kling_task(self, client, task_id: str, timeout: int = 300) -> str:
        """Poll a Kling async task until completion."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            result = await client.get(f"/videos/tasks/{task_id}")
            status = result.get("status", "")
            if status == "completed":
                return result.get("video", {}).get("url", "")
            elif status == "failed":
                raise RuntimeError(f"Kling task {task_id} failed: {result}")
            await asyncio.sleep(5)
        raise TimeoutError(f"Kling task {task_id} timed out after {timeout}s")

    async def _assemble_video(
        self,
        clips: list[str],
        narration: str,
        project: VideoProject,
        file_manager,
    ) -> str:
        """Assemble clips into final video using ffmpeg."""
        import subprocess
        from pathlib import Path

        project_dir = file_manager.project_dir(project.channel_id, project.project_id)

        # Create concat file for ffmpeg
        concat_path = project_dir / "concat_list.txt"
        with open(concat_path, "w") as f:
            for clip in clips:
                f.write(f"file '{clip}'\n")

        output_path = project_dir / "final_video.mp4"

        # Concatenate video clips
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_path),
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
        ]

        # Add narration audio if available
        if narration and Path(narration).exists():
            cmd.extend(["-i", narration, "-c:a", "aac", "-b:a", "192k", "-shortest"])
        else:
            cmd.extend(["-an"])

        cmd.append(str(output_path))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")

        return str(output_path)
