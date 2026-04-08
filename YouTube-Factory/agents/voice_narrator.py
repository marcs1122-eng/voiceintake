"""Voice Narrator Agent - generates narration audio using Atlas TTS."""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from core.state import VideoProject


class VoiceNarratorAgent(BaseAgent):
    """Generates voice narration using Atlas AI text-to-speech.

    Takes the full script narration text and converts it to audio using the
    channel-specific voice configuration (voice ID, speed, pitch, style).
    """

    name = "voice_narrator"

    async def process(self, project: VideoProject, context: dict[str, Any]) -> dict[str, Any]:
        if not self.validate_project(project, ["script"]):
            raise ValueError("Script required before voice narration")

        api_keys = context["api_keys"]
        file_manager = context["file_manager"]
        channel_cfg = self.get_channel_config(project)
        voice_cfg = channel_cfg.get("voice", {})

        voice_id = voice_cfg.get("voice_id", "atlas_default")
        speed = voice_cfg.get("speed", 1.0)
        pitch = voice_cfg.get("pitch", 0)
        style = voice_cfg.get("style", "narrative")

        atlas_key = api_keys.get("atlas", {}).get("api_key", "")
        atlas_url = api_keys.get("atlas", {}).get("base_url", "https://api.atlas.ai/v1")

        self.logger.info(
            f"Generating narration with voice '{voice_id}' "
            f"(speed={speed}, pitch={pitch}, style={style})"
        )

        from utils.api_client import APIClient
        client = APIClient(base_url=atlas_url, api_key=atlas_key, timeout=300.0)

        try:
            # Split script into chunks if too long (Atlas may have limits)
            chunks = self._split_script(project.script, max_chars=4000)
            audio_chunks: list[bytes] = []

            for i, chunk in enumerate(chunks):
                self.logger.debug(f"Narrating chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)")

                async def _generate_audio(text=chunk):
                    result = await client.post("/speech/generate", json={
                        "text": text,
                        "voice_id": voice_id,
                        "speed": speed,
                        "pitch": pitch,
                        "style": style,
                        "output_format": "mp3",
                        "quality": "high",
                        "sample_rate": 44100,
                    })
                    audio_url = result.get("audio_url", "")
                    if not audio_url:
                        raise RuntimeError(f"No audio URL in Atlas response: {result}")

                    import httpx
                    async with httpx.AsyncClient(timeout=120.0) as http:
                        resp = await http.get(audio_url)
                        resp.raise_for_status()
                        return resp.content

                audio_data = await self.retry(_generate_audio)
                audio_chunks.append(audio_data)

            # Concatenate audio chunks or save single chunk
            if len(audio_chunks) == 1:
                final_audio = audio_chunks[0]
            else:
                final_audio = await self._concatenate_audio(
                    audio_chunks, project, file_manager
                )

            filename = "narration.mp3"
            path = file_manager.save_bytes(
                project.channel_id, project.project_id, filename, final_audio
            )
            narration_path = str(path)

        finally:
            await client.close()

        project.narration_audio = narration_path

        project.log_agent_action(self.name, "narration_generated", {
            "voice_id": voice_id,
            "chunks": len(chunks),
            "audio_file": narration_path,
        })

        await self.emit("narration.completed", {
            "project_id": project.project_id,
            "audio_path": narration_path,
        })

        self.logger.info(f"Narration complete: {narration_path}")
        return {"narration_audio": narration_path}

    def _split_script(self, script: str, max_chars: int = 4000) -> list[str]:
        """Split script into chunks at sentence boundaries."""
        if len(script) <= max_chars:
            return [script]

        chunks = []
        current = ""
        sentences = script.replace("\n\n", "\n").split(". ")

        for sentence in sentences:
            candidate = current + sentence + ". " if current else sentence + ". "
            if len(candidate) > max_chars and current:
                chunks.append(current.strip())
                current = sentence + ". "
            else:
                current = candidate

        if current.strip():
            chunks.append(current.strip())

        return chunks

    async def _concatenate_audio(
        self,
        chunks: list[bytes],
        project: VideoProject,
        file_manager,
    ) -> bytes:
        """Concatenate audio chunks using ffmpeg."""
        import asyncio
        from pathlib import Path

        project_dir = file_manager.project_dir(project.channel_id, project.project_id)
        chunk_paths = []

        for i, chunk in enumerate(chunks):
            p = project_dir / f"narration_chunk_{i:03d}.mp3"
            p.write_bytes(chunk)
            chunk_paths.append(p)

        concat_file = project_dir / "audio_concat.txt"
        with open(concat_file, "w") as f:
            for p in chunk_paths:
                f.write(f"file '{p}'\n")

        output = project_dir / "narration_combined.mp3"
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file), "-c:a", "copy", str(output),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        result = output.read_bytes()

        # Cleanup temp chunks
        for p in chunk_paths:
            p.unlink(missing_ok=True)
        concat_file.unlink(missing_ok=True)
        output.unlink(missing_ok=True)

        return result
