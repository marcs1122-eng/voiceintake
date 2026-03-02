export async function POST(request) {
  const { text } = await request.json();
  if (!text) return new Response(JSON.stringify({ error: "No text" }), { status: 400, headers: { "Content-Type": "application/json" } });
  const apiKey = process.env.ELEVENLABS_API_KEY;
  if (!apiKey) return new Response(JSON.stringify({ error: "No API key" }), { status: 500, headers: { "Content-Type": "application/json" } });
  const voiceId = process.env.ELEVENLABS_VOICE_ID || "21m00Tcm4TlvDq8ikWAM";
  try {
    const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "xi-api-key": apiKey },
      body: JSON.stringify({ text, model_id: "eleven_flash_v2_5", voice_settings: { stability: 0.5, similarity_boost: 0.8, style: 0.15, use_speaker_boost: true } }),
    });
    if (!response.ok) { const err = await response.text(); console.error("ElevenLabs error:", err); return new Response(JSON.stringify({ error: "TTS failed" }), { status: 500, headers: { "Content-Type": "application/json" } }); }
    const audioBuffer = await response.arrayBuffer();
    return new Response(audioBuffer, { headers: { "Content-Type": "audio/mpeg", "Cache-Control": "no-cache" } });
  } catch (e) {
    console.error("TTS error:", e);
    return new Response(JSON.stringify({ error: "TTS request failed" }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
}
