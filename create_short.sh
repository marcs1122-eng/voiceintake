#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.claude/skills/topview-skill" && pwd)"
OUT_DIR="$(cd "$(dirname "$0")" && pwd)/output"
mkdir -p "$OUT_DIR"

echo "=== Step 1/3: Generating AI character image (9:16 vertical) ==="
IMAGE_URL=$(python3 "$SKILL_DIR/scripts/ai_image.py" run \
  --type text2image \
  --model "Nano Banana 2" \
  --prompt "Photorealistic portrait photo of a likeable relatable man in his early 30s, slightly overweight with a soft round face, warm gentle eyes, short messy brown hair, wearing a casual grey hoodie, sitting alone on a park bench at golden hour, looking slightly downward with a thoughtful vulnerable expression, soft cinematic lighting, shallow depth of field, upper body shot, 9:16 vertical composition" \
  --aspect-ratio "9:16" \
  --resolution "2K" \
  --output-dir "$OUT_DIR" -q)

echo "  Character image: $IMAGE_URL"

# Find the downloaded image
IMG_FILE=$(ls -t "$OUT_DIR"/*.{png,jpg,jpeg,webp} 2>/dev/null | head -1)
if [ -z "$IMG_FILE" ]; then
  echo "Error: No image file found in $OUT_DIR"
  exit 1
fi
echo "  Local file: $IMG_FILE"

echo ""
echo "=== Step 2/3: Animating into video (image-to-video, 9:16 YouTube Short) ==="
python3 "$SKILL_DIR/scripts/video_gen.py" run \
  --type i2v \
  --first-frame "$IMG_FILE" \
  --prompt "Slow cinematic motion, man sitting on park bench takes a deep breath and looks up at the sky with a bittersweet hopeful expression, gentle wind blows his hair, golden hour light shifts softly across his face, leaves drift slowly in background, melancholic yet beautiful atmosphere, shallow depth of field, emotional contemplative mood" \
  --model "Standard" \
  --resolution 1080 \
  --duration 10 \
  --sound on \
  --output-dir "$OUT_DIR"

echo ""
echo "=== Done! ==="
echo "Your YouTube Short is saved in: $OUT_DIR"
echo ""
echo "Upload the .mp4 file to YouTube Shorts (it's already 9:16 vertical)."
echo "Add your own emotional music track in YouTube Studio for best results."
