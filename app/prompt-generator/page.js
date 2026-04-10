"use client";

import { useState } from "react";

export default function PromptGeneratorPage() {
  var [theme, setTheme] = useState("");
  var [format, setFormat] = useState("short");
  var [loading, setLoading] = useState(false);
  var [error, setError] = useState(null);
  var [result, setResult] = useState(null);
  var [copied, setCopied] = useState("");

  async function generate(e) {
    if (e) e.preventDefault();
    if (!theme.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      var res = await fetch("/api/prompt-generator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ theme: theme.trim(), format: format }),
      });
      var data = await res.json();
      if (!res.ok || !data.ok) {
        setError(data.error || "Generation failed");
      } else {
        setResult(data);
      }
    } catch (err) {
      setError(err.message || "Network error");
    } finally {
      setLoading(false);
    }
  }

  function copy(text, key) {
    try {
      navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(function () {
        setCopied("");
      }, 1200);
    } catch (err) {
      // ignore
    }
  }

  function copyAll() {
    if (!result) return;
    var sb = result.storyboard;
    var lines = [];
    lines.push("TITLE: " + (sb.title || ""));
    lines.push("LOGLINE: " + (sb.logline || ""));
    lines.push("NARRATOR: " + (sb.narratorPersona || ""));
    lines.push("VISUAL STYLE: " + (sb.visualStyle || ""));
    lines.push("ASPECT RATIO: " + (sb.aspectRatio || ""));
    if (sb.characterBible && sb.characterBible.length) {
      lines.push("");
      lines.push("CHARACTER BIBLE:");
      sb.characterBible.forEach(function (c) {
        lines.push("- " + (c.name || "?") + ": " + (c.description || ""));
      });
    }
    if (sb.referenceAssets && sb.referenceAssets.length) {
      lines.push("");
      lines.push("REFERENCE ASSETS (upload to Higgsfield once):");
      sb.referenceAssets.forEach(function (r) {
        lines.push("- " + (r.slot || "") + " [" + (r.type || "") + "]: " + (r.purpose || ""));
        if (r.howToCreate) lines.push("    How to create: " + r.howToCreate);
      });
    }
    lines.push("");
    lines.push(
      "TOTAL DURATION: " +
        sb.totalDurationSeconds +
        "s across " +
        (sb.scenes || []).length +
        " scenes"
    );
    lines.push("");
    (sb.scenes || []).forEach(function (s) {
      lines.push("===== SCENE " + s.sceneNumber + " (" + s.duration + "s) =====");
      lines.push("CAMERA: " + (s.cameraDirection || ""));
      lines.push("");
      lines.push("OPENING IMAGE PROMPT:");
      lines.push(s.startImagePrompt || "");
      lines.push("");
      lines.push("SEEDANCE 2.0 PROMPT:");
      lines.push(s.seedancePrompt || "");
      lines.push("");
      lines.push("NARRATION (spoken words only):");
      lines.push(s.narration || "");
      lines.push("");
    });
    copy(lines.join("\n"), "all");
  }

  function copyNarration() {
    if (!result) return;
    var lines = (result.storyboard.scenes || []).map(function (s) {
      return s.narration || "";
    });
    copy(lines.join("\n\n"), "narration");
  }

  var sb = result && result.storyboard;

  return (
    <main
      style={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #0b1120 0%, #1e1b4b 100%)",
        color: "#e2e8f0",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        padding: "40px 20px",
      }}
    >
      <div style={{ maxWidth: 980, margin: "0 auto" }}>
        <header style={{ marginBottom: 28 }}>
          <h1
            style={{
              margin: 0,
              fontSize: 36,
              fontWeight: 800,
              background:
                "linear-gradient(90deg, #f472b6 0%, #a78bfa 50%, #60a5fa 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            AI Image + Video Prompt Generator
          </h1>
          <p style={{ margin: "8px 0 0", color: "#94a3b8", fontSize: 15 }}>
            Type a theme. Get a full storyboard tuned for <strong>Seedance 2.0</strong>
            {" "}(Higgsfield) — one opening image prompt + one Seedance prompt with
            embedded voiceover per scene, plus @image1/@audio1 reference locks
            for a consistent character and narrator across every clip.
          </p>
        </header>

        <form
          onSubmit={generate}
          style={{
            background: "#111827",
            border: "1px solid #1f2937",
            borderRadius: 14,
            padding: 16,
            boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
          }}
        >
          <label
            style={{
              display: "block",
              fontSize: 12,
              color: "#94a3b8",
              textTransform: "uppercase",
              letterSpacing: 1,
              marginBottom: 6,
            }}
          >
            Theme
          </label>
          <input
            type="text"
            value={theme}
            onChange={function (e) {
              setTheme(e.target.value);
            }}
            placeholder="e.g. Dogs speaking to other dog, humorous"
            autoFocus
            style={{
              width: "100%",
              boxSizing: "border-box",
              background: "#0b1120",
              border: "1px solid #334155",
              borderRadius: 10,
              padding: "14px 16px",
              color: "#f1f5f9",
              fontSize: 17,
              outline: "none",
            }}
          />

          <div
            style={{
              marginTop: 16,
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <FormatPill
              active={format === "short"}
              onClick={function () {
                setFormat("short");
              }}
              title="YouTube Short"
              sub="2 clips · 15s each · 9:16"
            />
            <FormatPill
              active={format === "video"}
              onClick={function () {
                setFormat("video");
              }}
              title="YouTube Video"
              sub="20 clips · 15s each · 16:9"
            />
            <div style={{ flex: 1 }} />
            <button
              type="submit"
              disabled={loading || !theme.trim()}
              style={{
                background:
                  loading || !theme.trim()
                    ? "#475569"
                    : "linear-gradient(90deg, #ec4899, #8b5cf6, #3b82f6)",
                color: "white",
                border: "none",
                borderRadius: 10,
                padding: "12px 26px",
                fontSize: 15,
                fontWeight: 700,
                cursor: loading || !theme.trim() ? "not-allowed" : "pointer",
                letterSpacing: 0.3,
              }}
            >
              {loading ? "Directing…" : "Generate Storyboard"}
            </button>
          </div>
        </form>

        {error && (
          <div
            style={{
              marginTop: 20,
              padding: 16,
              background: "#7f1d1d",
              border: "1px solid #dc2626",
              borderRadius: 10,
              color: "#fecaca",
            }}
          >
            {error}
          </div>
        )}

        {loading && (
          <div
            style={{
              marginTop: 24,
              textAlign: "center",
              color: "#94a3b8",
              fontSize: 14,
            }}
          >
            {format === "video"
              ? "Storyboarding a full 5-minute video. This can take up to 45 seconds…"
              : "Storyboarding your Short…"}
          </div>
        )}

        {sb && (
          <div style={{ marginTop: 28 }}>
            {/* Summary card */}
            <div
              style={{
                background: "#111827",
                border: "1px solid #1f2937",
                borderRadius: 14,
                padding: 22,
                marginBottom: 20,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: 12,
                  flexWrap: "wrap",
                }}
              >
                <div style={{ flex: 1, minWidth: 260 }}>
                  <div style={{ fontSize: 12, color: "#64748b", letterSpacing: 1, textTransform: "uppercase" }}>
                    {sb.format === "short" ? "YouTube Short" : "YouTube Video"} ·{" "}
                    {sb.totalDurationSeconds}s · {(sb.scenes || []).length} scenes
                  </div>
                  <h2 style={{ margin: "6px 0 4px", fontSize: 24 }}>{sb.title || "Untitled"}</h2>
                  <p style={{ margin: 0, color: "#cbd5e1", fontSize: 15, lineHeight: 1.5 }}>
                    {sb.logline || ""}
                  </p>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <ActionButton
                    onClick={copyAll}
                    label={copied === "all" ? "Copied!" : "Copy Full Script"}
                  />
                  <ActionButton
                    onClick={copyNarration}
                    label={copied === "narration" ? "Copied!" : "Copy Narration"}
                  />
                </div>
              </div>

              <div
                style={{
                  marginTop: 18,
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: 14,
                }}
              >
                <MetaBlock label="Narrator" value={sb.narratorPersona} />
                <MetaBlock label="Visual Style" value={sb.visualStyle} />
              </div>

              {sb.characterBible && sb.characterBible.length > 0 && (
                <div style={{ marginTop: 18 }}>
                  <div
                    style={{
                      fontSize: 12,
                      color: "#64748b",
                      textTransform: "uppercase",
                      letterSpacing: 1,
                      marginBottom: 8,
                    }}
                  >
                    Character Bible
                  </div>
                  <div style={{ display: "grid", gap: 8 }}>
                    {sb.characterBible.map(function (c, i) {
                      return (
                        <div
                          key={i}
                          style={{
                            background: "#0b1120",
                            border: "1px solid #1f2937",
                            borderRadius: 10,
                            padding: "10px 14px",
                            fontSize: 14,
                            color: "#cbd5e1",
                          }}
                        >
                          <strong style={{ color: "#f1f5f9" }}>{c.name}</strong>
                          {" — "}
                          {c.description}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Reference Assets panel */}
            {sb.referenceAssets && sb.referenceAssets.length > 0 && (
              <div
                style={{
                  background: "#111827",
                  border: "1px solid #a78bfa",
                  borderRadius: 14,
                  padding: 22,
                  marginBottom: 20,
                }}
              >
                <div
                  style={{
                    fontSize: 12,
                    color: "#a78bfa",
                    textTransform: "uppercase",
                    letterSpacing: 1,
                    fontWeight: 700,
                    marginBottom: 6,
                  }}
                >
                  Reference Assets to Upload to Higgsfield
                </div>
                <p style={{ margin: "0 0 14px", color: "#94a3b8", fontSize: 13, lineHeight: 1.5 }}>
                  Upload these once. Every scene&apos;s Seedance prompt will reference
                  them by @slot so the character and narrator voice stay identical
                  across every clip.
                </p>
                <div style={{ display: "grid", gap: 10 }}>
                  {sb.referenceAssets.map(function (r, i) {
                    return (
                      <div
                        key={i}
                        style={{
                          background: "#0b1120",
                          border: "1px solid #a78bfa",
                          borderRadius: 10,
                          padding: "12px 14px",
                          color: "#cbd5e1",
                          fontSize: 14,
                          lineHeight: 1.55,
                        }}
                      >
                        <div>
                          <strong style={{ color: "#a78bfa", fontSize: 15 }}>
                            {r.slot}
                          </strong>
                          {r.type && (
                            <span
                              style={{
                                marginLeft: 8,
                                fontSize: 11,
                                padding: "2px 8px",
                                background: "#1e293b",
                                borderRadius: 999,
                                color: "#94a3b8",
                              }}
                            >
                              {r.type}
                            </span>
                          )}
                        </div>
                        <div style={{ marginTop: 6 }}>
                          <strong>Purpose:</strong> {r.purpose}
                        </div>
                        {r.howToCreate && (
                          <div style={{ marginTop: 4 }}>
                            <strong>How to create:</strong> {r.howToCreate}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Scene list */}
            {(sb.scenes || []).map(function (s, idx) {
              return (
                <SceneCard
                  key={idx}
                  scene={s}
                  total={sb.scenes.length}
                  copied={copied}
                  onCopy={copy}
                />
              );
            })}
          </div>
        )}
      </div>
    </main>
  );
}

function FormatPill(props) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      style={{
        background: props.active ? "rgba(139,92,246,0.18)" : "#0b1120",
        border: props.active ? "1px solid #8b5cf6" : "1px solid #334155",
        borderRadius: 10,
        padding: "10px 14px",
        cursor: "pointer",
        textAlign: "left",
        color: "#e2e8f0",
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 700 }}>{props.title}</div>
      <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>
        {props.sub}
      </div>
    </button>
  );
}

function ActionButton(props) {
  return (
    <button
      onClick={props.onClick}
      style={{
        background: "#1f2937",
        border: "1px solid #334155",
        borderRadius: 8,
        padding: "8px 14px",
        color: "#e2e8f0",
        fontSize: 13,
        fontWeight: 600,
        cursor: "pointer",
      }}
    >
      {props.label}
    </button>
  );
}

function MetaBlock(props) {
  if (!props.value) return null;
  return (
    <div
      style={{
        background: "#0b1120",
        border: "1px solid #1f2937",
        borderRadius: 10,
        padding: "10px 14px",
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        {props.label}
      </div>
      <div style={{ marginTop: 4, fontSize: 14, color: "#cbd5e1" }}>
        {props.value}
      </div>
    </div>
  );
}

function SceneCard(props) {
  var s = props.scene;
  var n = s.sceneNumber;
  var copied = props.copied;
  var onCopy = props.onCopy;

  return (
    <div
      style={{
        background: "#111827",
        border: "1px solid #1f2937",
        borderRadius: 14,
        padding: 20,
        marginBottom: 16,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 14,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              background: "linear-gradient(90deg,#ec4899,#8b5cf6)",
              color: "white",
              fontWeight: 800,
              fontSize: 13,
              padding: "4px 10px",
              borderRadius: 999,
              letterSpacing: 0.4,
            }}
          >
            SCENE {n} / {props.total}
          </div>
          <div style={{ fontSize: 13, color: "#94a3b8" }}>{s.duration}s</div>
        </div>
        <div style={{ fontSize: 12, color: "#64748b" }}>
          {s.cameraDirection}
        </div>
      </div>

      <PromptBlock
        label="Opening Image Prompt (generate this image first)"
        value={s.startImagePrompt}
        tag={"img-start-" + n}
        copied={copied}
        onCopy={onCopy}
        accent="#60a5fa"
      />
      <PromptBlock
        label="Seedance 2.0 Prompt (paste into Higgsfield)"
        value={s.seedancePrompt}
        tag={"seedance-" + n}
        copied={copied}
        onCopy={onCopy}
        accent="#a78bfa"
      />
      <PromptBlock
        label="Narration (spoken words only)"
        value={s.narration}
        tag={"narr-" + n}
        copied={copied}
        onCopy={onCopy}
        accent="#f472b6"
      />
    </div>
  );
}

function PromptBlock(props) {
  if (!props.value) return null;
  var isCopied = props.copied === props.tag;
  return (
    <div
      style={{
        background: "#0b1120",
        border: "1px solid #1f2937",
        borderLeft: "3px solid " + (props.accent || "#8b5cf6"),
        borderRadius: 10,
        padding: "12px 14px",
        marginBottom: 10,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}
      >
        <div
          style={{
            fontSize: 11,
            color: props.accent || "#94a3b8",
            textTransform: "uppercase",
            letterSpacing: 1,
            fontWeight: 700,
          }}
        >
          {props.label}
        </div>
        <button
          onClick={function () {
            props.onCopy(props.value, props.tag);
          }}
          style={{
            background: "transparent",
            border: "1px solid #334155",
            color: "#cbd5e1",
            fontSize: 11,
            padding: "3px 8px",
            borderRadius: 6,
            cursor: "pointer",
          }}
        >
          {isCopied ? "Copied" : "Copy"}
        </button>
      </div>
      <div
        style={{
          color: "#e2e8f0",
          fontSize: 14,
          lineHeight: 1.55,
          whiteSpace: "pre-wrap",
        }}
      >
        {props.value}
      </div>
    </div>
  );
}
