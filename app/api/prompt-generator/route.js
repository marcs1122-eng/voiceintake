// AI Image + Video Prompt Generator
//
// Takes a theme (one word or a short phrase) and a format, and asks Claude
// to design a fully-storyboarded scene list for a YouTube Short or a
// 5-minute YouTube video.
//
// For each scene the generator returns:
//   - startImagePrompt   → prompt for the FIRST FRAME image (fed to an image
//                          model, then used as Veo 3.0 image-to-video input)
//   - endImagePrompt     → prompt for the LAST FRAME of this scene. This is
//                          ALSO the startImagePrompt of the next scene so the
//                          video flows seamlessly from clip to clip.
//   - videoPrompt        → Veo 3.0 motion/video prompt (what happens between
//                          the start and end frames)
//   - narration          → narrator VO line that plays over this scene
//   - cameraDirection    → camera notes (shot type, movement)
//   - duration           → seconds
//
// Format rules:
//   - "short" → 2 scenes × 15 s = 30 s total
//   - "video" → enough scenes to cover 5 min (300 s). Veo 3.0 produces ~8 s
//               clips, so target 38 scenes at 8 s each. Narration is pacey
//               so there's always audio.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 60;

function buildSystemPrompt(format) {
  var isShort = format === "short";
  var sceneCount = isShort ? 2 : 38;
  var sceneSeconds = isShort ? 15 : 8;
  var totalSeconds = isShort ? 30 : 300;
  var totalLabel = isShort ? "30-second YouTube Short" : "5-minute YouTube video";

  return [
    "You are a world-class AI video director and prompt engineer.",
    "Your job: turn a single theme into a fully-storyboarded, narrator-driven",
    "video, specified as a sequence of scenes that can be produced with an",
    "image generator (for keyframes) and Google Veo 3.0 (for image-to-video).",
    "",
    "TARGET FORMAT: " + totalLabel + ".",
    "TOTAL SCENES: exactly " + sceneCount + ".",
    "EACH SCENE DURATION: " + sceneSeconds + " seconds.",
    "TOTAL DURATION: " + totalSeconds + " seconds.",
    "",
    "CRITICAL CONTINUITY RULE:",
    "The endImagePrompt of scene N MUST be IDENTICAL to the startImagePrompt",
    "of scene N+1. This is how we chain Veo 3.0 clips into one continuous",
    "video: the last frame of a clip is the first frame of the next clip.",
    "Scene 1 has a fresh startImagePrompt. The final scene has an endImagePrompt",
    "that provides a satisfying visual resolution (it is not reused).",
    "",
    "IMAGE PROMPT GUIDELINES (for startImagePrompt and endImagePrompt):",
    "- Write a single rich paragraph, 40-80 words.",
    "- Describe subject, action/pose, setting, lighting, mood, color palette,",
    "  camera lens, composition, and rendering style (e.g. cinematic photo,",
    "  Pixar 3D, anime, claymation, etc.).",
    "- Lock in CONSISTENT character details (species, fur color, clothing,",
    "  personality quirks, proportions) so the same characters reappear across",
    "  scenes without drifting. Repeat those locked descriptors every time the",
    "  character is on screen.",
    "- Do NOT reference other scenes by number. Each prompt must be self-contained.",
    "",
    "VIDEO PROMPT GUIDELINES (for videoPrompt — Veo 3.0):",
    "- 30-60 words describing the MOTION between the start and end frames.",
    "- Specify: subject action, camera movement (dolly, pan, push in, orbit,",
    "  handheld, static), environmental motion (wind, dust, water, lighting",
    "  shift), and pacing.",
    "- Veo 3.0 is image-to-video, so assume the start frame is already fixed.",
    "- Do NOT restate the entire scene — only what changes/moves.",
    "- Include ambient audio cues when useful (e.g. 'ambient: light breeze,",
    "  distant barking').",
    "",
    "NARRATION GUIDELINES:",
    "- Write the narrator's actual spoken line for this scene.",
    "- Target ~2.3 words per second of scene time. For an " + sceneSeconds +
      "-second scene that is about " + Math.round(sceneSeconds * 2.3) + " words.",
    "- Keep the voice consistent across scenes (same narrator persona).",
    "- The narration across all scenes must read like ONE coherent script — a",
    "  beginning, middle, and end. Use the tone implied by the theme (humorous,",
    "  mysterious, heartfelt, educational, etc.).",
    "- Do not repeat the theme verbatim. Do not use stage directions in the",
    "  narration field — only the words the narrator says.",
    "",
    "CAMERA DIRECTION GUIDELINES:",
    "- One short line: shot type + movement + lens feel.",
    "  Example: 'Medium close-up, slow dolly-in, 50mm, shallow depth of field'.",
    "",
    "OUTPUT FORMAT — RETURN ONLY A JSON OBJECT, NO MARKDOWN, NO BACKTICKS:",
    "{",
    '  "title": "Short catchy title for the video",',
    '  "logline": "One-sentence summary of the story arc",',
    '  "narratorPersona": "Describe the narrator voice (e.g. warm 40s male, wry documentary tone)",',
    '  "visualStyle": "Global visual style that every scene must share (e.g. cinematic Pixar 3D, warm golden hour)",',
    '  "characterBible": [',
    '    { "name": "Rex", "description": "Locked visual description used in every prompt featuring this character" }',
    "  ],",
    '  "format": "' + format + '",',
    '  "totalDurationSeconds": ' + totalSeconds + ",",
    '  "scenes": [',
    "    {",
    '      "sceneNumber": 1,',
    '      "duration": ' + sceneSeconds + ",",
    '      "startImagePrompt": "...",',
    '      "endImagePrompt": "...",',
    '      "videoPrompt": "...",',
    '      "narration": "...",',
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
    "Produce the full storyboard now.",
    isShort
      ? "Remember: exactly 2 scenes, 15 seconds each, for a YouTube Short."
      : "Remember: exactly 38 scenes, 8 seconds each, for a 5-minute YouTube video.",
    "Every scene's endImagePrompt must equal the next scene's startImagePrompt.",
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

// Enforce the chaining rule even if the model drifts: copy scene N's
// endImagePrompt into scene N+1's startImagePrompt.
function enforceChain(storyboard) {
  if (!storyboard || !Array.isArray(storyboard.scenes)) return storyboard;
  var scenes = storyboard.scenes;
  for (var i = 1; i < scenes.length; i++) {
    var prevEnd = scenes[i - 1] && scenes[i - 1].endImagePrompt;
    if (prevEnd && scenes[i]) {
      scenes[i].startImagePrompt = prevEnd;
    }
    if (scenes[i]) {
      scenes[i].sceneNumber = i + 1;
    }
  }
  if (scenes[0]) scenes[0].sceneNumber = 1;
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

    storyboard = enforceChain(storyboard);

    // Safety net: ensure required top-level fields exist.
    if (!storyboard.format) storyboard.format = format;
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
