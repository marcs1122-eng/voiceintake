// AI Image + Video Prompt Generator for Seedance 2.0 (Higgsfield)
//
// Takes a theme (one word or a short phrase) and a format, and asks Claude
// to design a fully-storyboarded scene list for a YouTube Short or a
// 5-minute YouTube video, targeting Seedance 2.0 on Higgsfield.
//
// Seedance 2.0 key facts:
//   - Image-to-video with NATIVE synchronized audio in one pass
//     (voiceover, dialogue with lip-sync, SFX, ambient, music).
//   - Max clip length 15s, 720p on Higgsfield paid tier.
//   - Prompts up to 5,000 characters.
//   - Supports up to 12 reference files via @-tags: @image1, @video1, @audio1.
//   - Recommended structure: Subject -> Action -> Camera -> Environment
//     -> Lighting -> Audio/Mood, with [0-4s][4-10s][10-15s] beat markers.
//
// For each scene the generator returns:
//   - startImagePrompt   -> image prompt for the OPENING KEYFRAME. The user
//                           generates this image, then uploads it to Higgsfield
//                           as the starting frame for the Seedance 2.0 clip.
//   - seedancePrompt     -> the full Seedance 2.0 prompt with beat timeline
//                           markers, camera/lighting/environment, @image1 and
//                           @audio1 references, and an embedded voiceover line.
//   - narration          -> just the spoken words (no quotes, no delivery
//                           notes), kept for quick copy-paste and subtitling.
//   - cameraDirection    -> one-line camera summary.
//
// Format rules:
//   - "short" -> 2 scenes x 15 s = 30 s total, 9:16 vertical.
//   - "video" -> 20 scenes x 15 s = 300 s total, 16:9 horizontal.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function buildSystemPrompt(format) {
  var isShort = format === "short";
  var sceneCount = isShort ? 2 : 20;
  var sceneSeconds = 15;
  var totalSeconds = isShort ? 30 : 300;
  var totalLabel = isShort ? "30-second YouTube Short" : "5-minute YouTube video";
  var aspect = isShort ? "9:16 vertical" : "16:9 horizontal";
  var narrWords = Math.round(sceneSeconds * 2.3);

  return [
    "You are a world-class AI video director and prompt engineer for",
    "Seedance 2.0 (ByteDance) running on Higgsfield.",
    "",
    "ABOUT SEEDANCE 2.0 (CRITICAL FOR PROMPTING):",
    "- Image-to-video with NATIVE SYNCHRONIZED AUDIO in a single pass.",
    "- It generates video + voiceover + dialogue (with lip sync) + SFX +",
    "  ambient + music all from ONE text prompt plus reference files.",
    "- Max clip length 15 seconds, 720p on Higgsfield paid tier.",
    "- Prompts can be up to 5,000 characters.",
    "- Recommended structure inside each prompt:",
    "  Subject -> Action -> Camera -> Environment -> Lighting -> Audio / Mood",
    "- Supports timeline markers for multi-beat scenes: [0-3s] ... [3-6s] ...",
    "- Supports up to 12 reference files (images, video, audio) via @-tags:",
    "  @image1, @image2, @video1, @audio1. Use @image1 to lock a character",
    "  appearance and @audio1 to lock the narrator voice across EVERY scene.",
    "",
    "TARGET FORMAT: " + totalLabel + ", " + aspect + ".",
    "TOTAL SCENES: exactly " + sceneCount + ".",
    "EACH SCENE DURATION: " + sceneSeconds + " seconds.",
    "TOTAL DURATION: " + totalSeconds + " seconds.",
    "",
    "OUR WORKFLOW (what the creator will do):",
    "1. Generate the opening keyframe image for each scene using startImagePrompt.",
    "2. Upload 1-4 reference assets to Higgsfield ONCE: a locked character",
    "   reference image (@image1) and a locked narrator voice sample (@audio1).",
    "   You define what these references are in referenceAssets below.",
    "3. For each scene, upload the opening keyframe as the starting image and",
    "   paste seedancePrompt into the Seedance 2.0 prompt box.",
    "4. Seedance 2.0 produces a " + sceneSeconds + "s clip with video AND audio in one pass.",
    "",
    "REFERENCE ASSETS RULES:",
    "- Always define @image1 as the primary character reference (visual lock).",
    "- Always define @audio1 as the narrator voice reference (voice lock).",
    "- If the theme has a second recurring character, define @image2.",
    "- If there is a signature sound/music bed, define @audio2.",
    "- Max 4 references total. Keep it simple.",
    "- For each reference, describe what the creator should generate/record,",
    "  so they know exactly what file to upload to that @slot.",
    "",
    "IMAGE PROMPT GUIDELINES (startImagePrompt):",
    "- This is the OPENING KEYFRAME only. 40-80 word paragraph.",
    "- Include: subject, pose, setting, composition, lens, lighting, mood,",
    "  color palette, rendering style.",
    "- Repeat the locked character descriptors VERBATIM from the character",
    "  bible every time that character appears.",
    "- Use " + aspect + " framing.",
    "- Do NOT reference other scenes by number.",
    "",
    "SEEDANCE 2.0 PROMPT GUIDELINES (seedancePrompt) - THIS IS THE CORE:",
    "Each seedancePrompt is ~200-400 words and MUST follow this template:",
    "",
    "```",
    "[Subject with locked character descriptors] [opening pose / action]. Reference @image1 for character appearance.",
    "",
    "[0-4s] [Beat 1: specific action, micro-expression, subtle movement, camera move]",
    "[4-10s] [Beat 2: escalating action, reaction, camera move]",
    "[10-15s] [Beat 3: resolution beat, final pose or gesture, camera move]",
    "",
    "Camera: [shot type + movement + lens, e.g. 'handheld medium shot, slow push-in, 35mm, shallow depth of field'].",
    "Environment: [setting details, props, background motion like wind, dust, crowd].",
    "Lighting: [quality, direction, color temperature, mood].",
    "",
    'Voiceover (narrator, voice referenced from @audio1): "<the line>" -- [delivery notes: tone, tempo, pause cues].',
    "",
    "Ambient: [2-4 layered SFX / ambient cues].",
    "Music: [genre, instrumentation, mood, bpm] (optional, one line).",
    "Style: [render style, MUST match the global visualStyle].",
    "```",
    "",
    "VOICEOVER RULES (inside seedancePrompt):",
    "- Pacing: ~2.3 words per second. For " + sceneSeconds + "s clip aim for ~" +
      narrWords + " words.",
    "- Keep sentences short (5-10 words) for clean lip-sync timing.",
    "- Always reference @audio1 for the narrator voice so voice stays identical.",
    "- Include delivery notes (tone, tempo, pause cues) after the quoted line.",
    "- The voiceover is a NARRATOR speaking OVER the scene (not the character",
    "  on screen), unless the theme explicitly calls for in-scene dialogue.",
    "",
    "NARRATION FIELD (separate, for convenience):",
    "- Also output the spoken line(s) verbatim in the narration field, with",
    "  NO delivery notes and NO quotes, so the creator can copy just the",
    "  words for subtitling or a TTS fallback.",
    "",
    "CONTINUITY RULES:",
    "- Character descriptors in character bible are LAW. Repeat verbatim.",
    "- visualStyle and lighting mood are LAW. Every scene matches.",
    "- Narration across ALL scenes reads as ONE script: hook -> development",
    "  -> payoff -> CTA.",
    "- Use the tone implied by the theme (humorous, heartfelt, educational,",
    "  mysterious, etc.).",
    "",
    "CAMERA DIRECTION (scene-level summary, short):",
    "- One short line summarizing the dominant camera behavior of the clip.",
    "",
    "OUTPUT FORMAT - RETURN ONLY A JSON OBJECT, NO MARKDOWN, NO BACKTICKS:",
    "{",
    '  "title": "Short catchy title",',
    '  "logline": "One-sentence summary of the arc",',
    '  "narratorPersona": "Describe the narrator voice, e.g. warm 40s male, dry documentary tone",',
    '  "visualStyle": "Global visual style every scene must share",',
    '  "aspectRatio": "' + (isShort ? "9:16" : "16:9") + '",',
    '  "characterBible": [',
    '    { "name": "Rex", "description": "Locked visual description" }',
    "  ],",
    '  "referenceAssets": [',
    "    {",
    '      "slot": "@image1",',
    '      "type": "image",',
    '      "purpose": "Primary character visual lock",',
    '      "howToCreate": "Generate a clean portrait of <character> using this prompt: <image prompt>"',
    "    },",
    "    {",
    '      "slot": "@audio1",',
    '      "type": "audio",',
    '      "purpose": "Narrator voice lock",',
    '      "howToCreate": "Record or TTS 15-30 seconds of the narrator reading any line in the target persona, save as mp3/wav"',
    "    }",
    "  ],",
    '  "format": "' + format + '",',
    '  "totalDurationSeconds": ' + totalSeconds + ",",
    '  "scenes": [',
    "    {",
    '      "sceneNumber": 1,',
    '      "duration": ' + sceneSeconds + ",",
    '      "startImagePrompt": "...",',
    '      "seedancePrompt": "... (full Seedance 2.0 prompt with @image1, @audio1 references and voiceover embedded) ...",',
    '      "narration": "Just the spoken words, no quotes or delivery notes",',
    '      "cameraDirection": "..."',
    "    }",
    "  ]",
    "}",
    "",
    "RESPOND WITH ONLY THE JSON. No prose, no markdown fences."
  ].join("\n");
}

function buildUserPrompt(theme, format) {
  var isShort = format === "short";
  return [
    "THEME: " + theme,
    "",
    "Produce the full Seedance 2.0 storyboard now.",
    isShort
      ? "Remember: exactly 2 scenes, 15 seconds each, for a YouTube Short (9:16)."
      : "Remember: exactly 20 scenes, 15 seconds each, for a 5-minute YouTube video (16:9).",
    "Every seedancePrompt must reference @image1 for the character and @audio1",
    "for the narrator voice so they stay identical across all clips.",
    "Lock character/visual details in the character bible and reuse them verbatim."
  ].join("\n");
}

function extractJson(text) {
  var s = text.trim();
  if (s.startsWith("```")) {
    s = s.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
  }
  try {
    return JSON.parse(s);
  } catch (e) {
    var m = s.match(/\{[\s\S]*\}/);
    if (m) return JSON.parse(m[0]);
    throw e;
  }
}

function renumberScenes(storyboard) {
  if (!storyboard || !Array.isArray(storyboard.scenes)) return storyboard;
  for (var i = 0; i < storyboard.scenes.length; i++) {
    if (storyboard.scenes[i]) storyboard.scenes[i].sceneNumber = i + 1;
  }
  return storyboard;
}

export async function POST(request) {
  var body;
  try {
    body = await request.json();
  } catch (e) {
    return json({ error: "Invalid JSON body" }, 400);
  }

  var theme = (body.theme || "").toString().trim();
  var format = (body.format || "short").toString().trim().toLowerCase();

  if (!theme) {
    return json({ error: "Please provide a theme." }, 400);
  }
  if (format !== "short" && format !== "video") {
    return json({ error: "format must be 'short' or 'video'" }, 400);
  }

  var apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return json({ error: "ANTHROPIC_API_KEY is not configured." }, 500);
  }

  var systemPrompt = buildSystemPrompt(format);
  var userPrompt = buildUserPrompt(theme, format);

  try {
    var res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: format === "short" ? 4000 : 16000,
        system: systemPrompt,
        messages: [{ role: "user", content: userPrompt }]
      })
    });

    if (!res.ok) {
      var errText = await res.text();
      console.error("Anthropic error:", errText);
      return json({ error: "AI request failed: " + res.status }, 500);
    }

    var data = await res.json();
    var text =
      data && data.content && data.content[0] && data.content[0].text
        ? data.content[0].text
        : "";

    var storyboard;
    try {
      storyboard = extractJson(text);
    } catch (pe) {
      console.error("JSON parse failure:", text.slice(0, 400));
      return json({ error: "Could not parse AI response as JSON." }, 500);
    }

    storyboard = renumberScenes(storyboard);

    // Safety net: ensure required top-level fields exist.
    if (!storyboard.format) storyboard.format = format;
    if (!storyboard.aspectRatio) storyboard.aspectRatio = format === "short" ? "9:16" : "16:9";
    if (!storyboard.totalDurationSeconds) {
      storyboard.totalDurationSeconds = format === "short" ? 30 : 300;
    }
    if (!Array.isArray(storyboard.scenes)) storyboard.scenes = [];

    return json({ ok: true, theme: theme, storyboard: storyboard });
  } catch (e) {
    console.error("prompt-generator error:", e);
    return json({ error: "Generation failed: " + e.message }, 500);
  }
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "Content-Type": "application/json" }
  });
}
