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
      // optimize_streaming_latency=3: max latency reduction without disabling text normalizer
      // (level 4 disables normalizer \u2014 risks mispronouncing medical terms / numbers)
      // output_format=mp3_22050_32: smallest valid MP3 \u2014 phone audio is 8kHz anyway,
      // 22050Hz is plenty, 32kbps cuts file size ~75% vs default (faster Twilio download)
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}/stream?optimize_streaming_latency=3&output_format=mp3_22050_32`,
      {
        method: 'POST',
        headers: {
          'Accept': 'audio/mpeg',
          'Content-Type': 'application/json',
          'xi-api-key': process.env.ELEVENLABS_API_KEY,
        },
        body: JSON.stringify({
          text,
          model_id: 'eleven_flash_v2_5',
          voice_settings: {
            stability: 0.75,          // Higher stability = more consistent, less compute
            similarity_boost: 0.80,   // Close to original voice
            style: 0,                 // KEY FIX: style > 0 adds a render pass that causes
                                      // both ~100-200ms extra latency AND audio artifacts
                                      // (this was the source of the "background noise")
            use_speaker_boost: false, // Saves ~20-50ms \u2014 audible difference is negligible on phone
          },
        }),
      }
    );

    if (!response.ok) {
      console.error('ElevenLabs error:', response.status, await response.text());
      return new NextResponse('ElevenLabs error', { status: 500 });
    }

    // Stream the response body directly instead of buffering with arrayBuffer()
    // This means Twilio starts receiving audio bytes as ElevenLabs generates them
    // instead of waiting for the entire clip to finish before sending anything
    return new NextResponse(response.body, {
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
