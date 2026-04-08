"""Thumbnail Generator Agent - creates click-worthy thumbnails."""

from __future__ import annotations

import json
from typing import Any

import anthropic

from agents.base import BaseAgent
from core.state import VideoProject


class ThumbnailGeneratorAgent(BaseAgent):
    """Generates eye-catching thumbnails optimized for CTR.

    Creates thumbnails using Higgsfield that match the channel's visual style,
    with text overlays, dramatic compositions, and platform-optimized sizing.
    """

    name = "thumbnail_generator"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["title"]):
            raise ValueError("Title required before thumbnail generation")

        api_keys = context["api_keys"]
        file_manager = context["file_manager"]
        channel_cfg = self.get_channel_config(project)
        thumb_cfg = channel_cfg.get("visuals", {}).get("thumbnail", {})
        visual_cfg = channel_cfg.get("visuals", {})

        style = thumb_cfg.get("style", "dramatic")
        text_position = thumb_cfg.get("text_position", "bottom_third")
        font = thumb_cfg.get("font", "Impact")
        overlay = thumb_cfg.get("overlay", "none")
        prefix = visual_cfg.get("image_prompt_prefix", "")

        self.logger.info(f"Generating thumbnail for '{project.title}'")

        # Use LLM to design the thumbnail concept
        client = anthropic.AsyncAnthropic(api_key=api_keys["anthropic"]["api_key"])

        design_prompt = f"""Design a YouTube thumbnail for this video:
Title: {project.title}
Channel style: {style}
Tone: {channel_cfg.get('tone', 'engaging')}
Topic: {project.topic}

Create a detailed image generation prompt for a thumbnail that:
1. Immediately communicates the video topic
2. Creates curiosity/emotional response
3. Works at small sizes (mobile)
4. Uses {text_position} text placement area
5. Follows the {style} aesthetic

Also provide:
- Suggested overlay text (3-5 words max, high impact)
- Text color that contrasts with the image
- Whether to include a face/expression element

Output as JSON:
{{
  "image_prompt": "detailed prompt for Higgsfield",
  "overlay_text": "SHORT TEXT",
  "text_color": "#FFFFFF",
  "text_stroke_color": "#000000",
  "include_face": true,
  "composition_notes": "brief description"
}}"""

        async def _design():
            response = await client.messages.create(
                model=api_keys["anthropic"].get("model", "claude-sonnet-4-6"),
                max_tokens=1024,
                messages=[{"role": "user", "content": design_prompt}],
            )
            return response.content[0].text

        raw = await self.retry(_design)

        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]

        design = json.loads(raw.strip())

        # Generate the base thumbnail image via Higgsfield
        from utils.api_client import APIClient
        higgsfield_key = api_keys.get("higgsfield", {}).get("api_key", "")
        higgsfield_url = api_keys.get("higgsfield", {}).get("base_url", "")

        hf_client = APIClient(base_url=higgsfield_url, api_key=higgsfield_key, timeout=180.0)

        try:
            full_prompt = prefix + design.get("image_prompt", "thumbnail image")

            result = await hf_client.post("/images/generate", json={
                "model": "nano-banana-pro",
                "prompt": full_prompt,
                "aspect_ratio": "16:9",
                "num_images": 1,
                "quality": "high",
                "width": 1280,
                "height": 720,
                "output_format": "png",
            })

            image_url = result.get("images", [{}])[0].get("url", "")
            if image_url:
                import httpx
                async with httpx.AsyncClient(timeout=60.0) as http:
                    resp = await http.get(image_url)
                    resp.raise_for_status()
                    image_data = resp.content

                # Save base thumbnail
                base_path = file_manager.save_bytes(
                    project.channel_id, project.project_id, "thumbnail_base.png", image_data
                )

                # Add text overlay using Pillow
                final_path = await self._add_text_overlay(
                    base_path=str(base_path),
                    text=design.get("overlay_text", ""),
                    text_color=design.get("text_color", "#FFFFFF"),
                    stroke_color=design.get("text_stroke_color", "#000000"),
                    position=text_position,
                    font_name=font,
                    project=project,
                    file_manager=file_manager,
                )

                project.thumbnail_path = final_path
            else:
                self.logger.warning("No thumbnail image generated")
                project.thumbnail_path = ""
                final_path = ""

        finally:
            await hf_client.close()

        project.log_agent_action(self.name, "thumbnail_generated", {
            "path": project.thumbnail_path,
            "overlay_text": design.get("overlay_text", ""),
        })

        await self.emit("thumbnail.completed", {
            "project_id": project.project_id,
            "path": project.thumbnail_path,
        })

        self.logger.info(f"Thumbnail generated: {project.thumbnail_path}")
        return {"thumbnail_path": project.thumbnail_path, "design": design}

    async def _add_text_overlay(
        self,
        base_path: str,
        text: str,
        text_color: str,
        stroke_color: str,
        position: str,
        font_name: str,
        project: VideoProject,
        file_manager,
    ) -> str:
        """Add text overlay to thumbnail using Pillow."""
        from PIL import Image, ImageDraw, ImageFont
        from pathlib import Path

        img = Image.open(base_path)
        draw = ImageDraw.Draw(img)

        # Try to load the specified font, fall back to default
        font_size = int(img.height * 0.08)
        try:
            font = ImageFont.truetype(f"/usr/share/fonts/truetype/{font_name.lower()}.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        if not text:
            # No overlay needed, just return base
            return base_path

        # Calculate text position
        bbox = draw.textbbox((0, 0), text.upper(), font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (img.width - text_w) // 2

        position_map = {
            "top_third": int(img.height * 0.1),
            "center": (img.height - text_h) // 2,
            "bottom_third": int(img.height * 0.75),
        }
        y = position_map.get(position, int(img.height * 0.75))

        # Draw text with stroke
        draw.text(
            (x, y),
            text.upper(),
            font=font,
            fill=text_color,
            stroke_width=3,
            stroke_fill=stroke_color,
        )

        # Save final thumbnail
        output_path = Path(base_path).parent / "thumbnail_final.png"
        img.save(output_path, "PNG", quality=95)

        return str(output_path)
