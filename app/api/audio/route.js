import { NextResponse } from 'next/server';

export async function GET(request) {
  const url = new URL(request.url);
  const text = url.searchParams.get('text') || '';

  if (!text) {
    return new NextResponse('Missing text', { status: 400 });
  }

  try {
    const voiceId = process.env.ELEVENLABS_VOICE_ID;
    if (!voiceId) {
      console.error('ELEVENLABS_VOICE_ID env var is not set!');
      return new NextResponse('Voice configuration error', { status: 500 });
    }

    const response = await fetch(
      // optimize_streaming_latency=4: maximum latency reduction (disables text normalizer)
      // Safe for medical intake — questions are naturally phrased, not raw medical terms
      // output_format=ulaw_8000: native Twilio telephony format — eliminates transcoding
      // overhead and significantly reduces latency vs mp3
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}/stream?optimize_streaming_latency=4&output_format=ulaw_8000`,
      {
        method: 'POST',
        headers: {
          'Accept': 'audio/basic',
          'Content-Type': 'application/json',
          'xi-api-key': process.env.ELEVENLABS_API_KEY,
        },
        body: JSON.stringify({
          text,
          model_id: 'eleven_flash_v2_5',
          voice_settings: {
            stability: 0.55,          // Lower = more natural conversational variance (ElevenLabs rec)
            similarity_boost: 0.80,   // Close to original voice
            style: 0,                 // style > 0 adds ~100-200ms latency + artifacts
            use_speaker_boost: false,  // Saves ~20-50ms
          },
        }),
      }
    );

    if (!response.ok) {
      console.error('ElevenLabs error:', response.status, await response.text());
      return new NextResponse('ElevenLabs error', { status: 500 });
    }

    // Stream directly — Twilio gets audio bytes as ElevenLabs generates them
    return new NextResponse(response.body, {
      headers: {
        'Content-Type': 'audio/basic',
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (err) {
    console.error('Audio generation error:', err);
    return new NextResponse('Audio generation failed', { status: 500 });
  }
}
