import { NextResponse } from 'next/server';

export async function GET(request) {
  const url = new URL(request.url);
  const text = url.searchParams.get('text') || '';

  if (!text) {
    return new NextResponse('Missing text', { status: 400 });
  }

  try {
    const voiceId = process.env.ELEVENLABS_VOICE_ID || 'kSDv9EbJ41pJUICMEOOu';

    const response = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}/stream`,
      {
        method: 'POST',
        headers: {
          'Accept': 'audio/mpeg',
          'Content-Type': 'application/json',
          'xi-api-key': process.env.ELEVENLABS_API_KEY,
        },
        body: JSON.stringify({
          text: text,
          model_id: 'eleven_flash_v2_5',
          voice_settings: {
            stability: 0.5,
            similarity_boost: 0.75,
            style: 0.3,
            use_speaker_boost: true,
          },
        }),
      }
    );

    if (!response.ok) {
      console.error('ElevenLabs error:', response.status, await response.text());
      return new NextResponse('ElevenLabs error', { status: 500 });
    }

    const audioBuffer = await response.arrayBuffer();

    return new NextResponse(audioBuffer, {
      headers: {
        'Content-Type': 'audio/mpeg',
        'Cache-Control': 'public, max-age=3600',
      },
    });

  } catch (err) {
    console.error('Audio generation error:', err);
    return new NextResponse('Audio generation failed', { status: 500 });
  }
}
