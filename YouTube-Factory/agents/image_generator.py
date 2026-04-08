"""Image Generator Agent - generates images using Higgsfield/Nano Banana Pro."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agents.base import BaseAgent
from core.state import VideoProject


class ImageGeneratorAgent(BaseAgent):
    """Generates images from prompts using the Higgsfield Python SDK (Nano Banana Pro).

    Processes image prompts in batches, handles rate limiting, and saves
    generated images to the project output directory.
    """

    name = "image_generator"

    BATCH_SIZE = 4
    BATCH_DELAY = 2.0  # seconds between batches

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["image_prompts"]):
            raise ValueError("Image prompts required before image generation")

        api_keys = context["api_keys"]
        file_manager = context["file_manager"]
        channel_cfg = self.get_channel_config(project)
        visual_cfg = channel_cfg.get("visuals", {})
        aspect_ratio = visual_cfg.get("aspect_ratio", "16:9")

        higgsfield_key = api_keys.get("higgsfield", {}).get("api_key", "")
        base_url = api_keys.get("higgsfield", {}).get("base_url", "https://api.higgsfield.ai/v1")

        self.logger.info(
            f"Generating {len(project.image_prompts)} images via Higgsfield Nano Banana Pro"
        )

        generated_paths: list[str] = []

        # Process in batches to respect rate limits
        for batch_start in range(0, len(project.image_prompts), self.BATCH_SIZE):
            batch = project.image_prompts[batch_start:batch_start + self.BATCH_SIZE]
            batch_tasks = []

            for i, prompt in enumerate(batch):
                idx = batch_start + i
                batch_tasks.append(
                    self._generate_single(
                        prompt=prompt,
                        index=idx,
                        aspect_ratio=aspect_ratio,
                        api_key=higgsfield_key,
                        base_url=base_url,
                        project=project,
                        file_manager=file_manager,
                    )
                )

            results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Image {batch_start + j} failed: {result}")
                    project.add_error(f"Image generation failed for prompt {batch_start + j}")
                else:
                    generated_paths.append(result)

            # Delay between batches
            if batch_start + self.BATCH_SIZE < len(project.image_prompts):
                await asyncio.sleep(self.BATCH_DELAY)

        project.generated_images = generated_paths

        project.log_agent_action(self.name, "images_generated", {
            "total_prompts": len(project.image_prompts),
            "successful": len(generated_paths),
            "failed": len(project.image_prompts) - len(generated_paths),
        })

        await self.emit("images.completed", {
            "project_id": project.project_id,
            "count": len(generated_paths),
        })

        self.logger.info(
            f"Generated {len(generated_paths)}/{len(project.image_prompts)} images"
        )
        return {"generated_images": generated_paths}

    async def _generate_single(
        self,
        prompt: str,
        index: int,
        aspect_ratio: str,
        api_key: str,
        base_url: str,
        project: VideoProject,
        file_manager,
    ) -> str:
        """Generate a single image via Higgsfield SDK."""
        from utils.api_client import APIClient

        client = APIClient(base_url=base_url, api_key=api_key, timeout=180.0)

        try:
            # Higgsfield Nano Banana Pro API call
            result = await client.post("/images/generate", json={
                "model": "nano-banana-pro",
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "num_images": 1,
                "quality": "high",
                "output_format": "png",
            })

            image_url = result.get("images", [{}])[0].get("url", "")
            if not image_url:
                raise RuntimeError(f"No image URL in response: {result}")

            # Download the image
            import httpx
            async with httpx.AsyncClient(timeout=60.0) as http:
                resp = await http.get(image_url)
                resp.raise_for_status()
                image_data = resp.content

            # Save to project directory
            filename = f"scene_{index:03d}.png"
            path = file_manager.save_bytes(
                project.channel_id, project.project_id, filename, image_data
            )

            self.logger.debug(f"Saved image {index}: {path}")
            return str(path)

        finally:
            await client.close()
