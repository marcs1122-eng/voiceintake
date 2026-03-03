"use client";
import { useState, useRef, useEffect, useCallback } from "react";

const PRACTICE = "Global Neuro & Spine Institute";
const ACKS = ["Got it.", "Thank you.", "Okay, noted.", "Perfect.", "Alright."];
const ack = () => ACKS[Math.floor(Math.random() * ACKS.length)];

const FLOWS = {
  new: [
    { s: "Demographics", q: "Let us start with your full name, first and last please.", f: "full_name", t: "text" },
    { s: "Demographics", q: "Could you spell your last name for me?", f: "last_name_spell", t: "text" },
    { s: "Demographics", q: "What is your date of birth?", f: "dob", t: "text" },
    { s: "Demographics", q: "Your height?", f: "height", t: "text" },
    { s: "Demographics", q: "And your current weight?", f: "weight", t: "text" },
    { s: "Pain History", q: "Tell me in your own words, what is the main reason you are coming in today?", f: "chief_complaint", t: "text" },
    { s: "Pain History", q: "Do you know what caused this pain? A car accident, a fall, or something else?", f: "cause", t: "text" },
    { s: "Pain History", q: "When did this happen, do you remember the approximate date?", f: "accident_date", t: "text" },
    { s: "Pain History", q: "Did you have any pain in that area before this happened?", f: "prior_pain", t: "yn" },
    { s: "Pain History", q: "Where exactly is your pain located?", f: "pain_loc", t: "text" },
    { s: "Pain History", q: "Does the pain travel or radiate anywhere, like down your arm or leg?", f: "pain_rad", t: "text" },
    { s: "Pain History", q: "What makes your pain worse?", f: "pain_worse", t: "text" },
    { s: "Pain History", q: "What helps make it better?", f: "pain_better", t: "text" },
    { s: "Pain History", q: "How would you describe your pain: sharp, burning, shooting, achy, pressure, or something else?", f: "pain_desc", t: "text" },
    { s: "Pain History", q: "On a scale of 0 to 10, how would you rate your pain right now?", f: "pain_sev", t: "scale" },
    { s: "Treatment", q: "What treatments have you tried so far: therapy, injections, medications, or surgery?", f: "treatments", t: "text" },
    { s: "Treatment", q: "What medications are you currently taking?", f: "meds", t: "text" },
    { s: "Treatment", q: "Do you have any allergies to medications or other substances?", f: "allergies", t: "text" },
    { s: "Medical History", q: "Do you have any medical conditions: diabetes, high blood pressure, heart disease, or anything else?", f: "conditions", t: "text" },
    { s: "Medical History", q: "Have you had any surgeries?", f: "surgeries", t: "text" },
    { s: "Medical History", q: "Any hospitalizations?", f: "hosps", t: "text" },
    { s: "Family History", q: "Family history of cancer, diabetes, heart disease, or stroke?", f: "fam_hx", t: "text" },
    { s: "Social History", q: "What is your marital status?", f: "marital", t: "choice", o: ["Married", "Single", "Divorced", "Separated"] },
    { s: "Social History", q: "Are you currently employed? What do you do?", f: "employment", t: "text" },
    { s: "Social History", q: "Do you smoke or use tobacco?", f: "smoking", t: "yn" },
    { s: "Social History", q: "How many packs per day, and for how many years?", f: "smoke_detail", t: "text", c: (d) => d.smoking === "Yes" },
    { s: "Social History", q: "Do you drink alcohol?", f: "alcohol", t: "yn" },
    { s: "Social History", q: "How much and how often?", f: "alc_detail", t: "text", c: (d) => d.alcohol === "Yes" },
    { s: "Social History", q: "Are you applying for disability?", f: "disability", t: "yn" },
    { s: "Review of Systems", q: "Quick symptom check. Any recent weight changes, weakness, fatigue, or fever?", f: "ros_const", t: "text" },
    { s: "Review of Systems", q: "Any chest pain, shortness of breath, or palpitations?", f: "ros_cardio", t: "text" },
    { s: "Review of Systems", q: "Any numbness, tingling, headaches, or memory issues?", f: "ros_neuro", t: "text" },
    { s: "Review of Systems", q: "Any other joint pain, stiffness, or loss of range of motion?", f: "ros_msk", t: "text" },
    { s: "Review of Systems", q: "How about your mood. Any anxiety, depression, or mood changes?", f: "ros_psych", t: "text" },
    { s: "Review of Systems", q: "Any other symptoms: vision, hearing, breathing, stomach, or skin?", f: "ros_other", t: "text" },
    { s: "Safety", q: "Is there any chance you could be pregnant?", f: "pregnant", t: "text" },
    { s: "Consent", q: "Last step. By completing this intake you authorize Global Neuro and Spine Institute to release medical information to process your insurance claims. Do you understand and agree?", f: "consent", t: "yn" },
  ],
  followup: [
    { s: "Identification", q: "Welcome back! Can I get your full name?", f: "full_name", t: "text" },
    { s: "Current Visit", q: "What is bringing you in today?", f: "chief_complaint", t: "text" },
    { s: "Current Visit", q: "Where is your pain located?", f: "pain_loc", t: "text" },
    { s: "Current Visit", q: "What makes it worse?", f: "pain_worse", t: "text" },
    { s: "Current Visit", q: "What makes it better?", f: "pain_better", t: "text" },
    { s: "Current Visit", q: "How would you describe the pain?", f: "pain_desc", t: "text" },
    { s: "Current Visit", q: "On a scale of 0 to 10, how severe is it right now?", f: "pain_sev", t: "scale" },
    { s: "Last Visit", q: "Did you have a procedure during your last visit?", f: "had_proc", t: "yn" },
    { s: "Last Visit", q: "How much relief did the procedure give you?", f: "proc_relief", t: "choice", o: ["Less than 25%", "25-50%", "50-75%", "More than 75%"], c: (d) => d.had_proc === "Yes" },
    { s: "Changes", q: "Any new medications since your last visit?", f: "new_meds", t: "text" },
    { s: "Changes", q: "Any new illnesses, injuries, surgeries, or hospitalizations?", f: "new_cond", t: "text" },
    { s: "Changes", q: "Any changes to your family medical history?", f: "fam_chg", t: "text" },
    { s: "Changes", q: "Changes in marital status, employment, or substance use?", f: "soc_chg", t: "text" },
    { s: "Changes", q: "Are you applying for disability?", f: "disability", t: "yn" },
    { s: "Review of Systems", q: "Any new symptoms: heart, breathing, stomach, vision, mood, numbness, or tingling?", f: "ros", t: "text" },
    { s: "Review of Systems", q: "Anything else you want the doctor to know?", f: "ros_other", t: "text" },
  ],
};

async function speakEL(text) {
  try {
    const res = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error("TTS failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    return new Promise((resolve) => {
      const audio = new Audio(url);
      audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
      audio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
      audio.play().catch(() => resolve());
    });
  } catch (e) {
    return new Promise((resolve) => {
      if (!window.speechSynthesis) { resolve(); return; }
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 0.95;
      u.onend = resolve;
      u.onerror = resolve;
      window.speechSynthesis.speak(u);
    });
  }
}

export default function VoiceIntake() {
  const [screen, setScreen] = useState("home");
  const [type, setType] = useState(null);
  const [step, setStep] = useState(0);
  const [resp, setResp] = useState({});
  const [input, setInput] = useState("");
  const [chat, setChat] = useState([]);
  const [voiceOn, setVoiceOn] = useState(true);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [interim, setInterim] = useState("");

  const chatRef = useRef(null);
  const recRef = useRef(null);
  const timerRef = useRef(null);
  const busyRef = useRef(false);
  const pendingRef = useRef("");
  const stepRef = useRef(0);
  const respRef = useRef({});
  const voiceOnRef = useRef(true);

  const flow = type ? FLOWS[type] : [];

  // Keep refs in sync with state
  useEffect(() => { stepRef.current = step; }, [step]);
  useEffect(() => { respRef.current = resp; }, [resp]);
  useEffect(() => { voiceOnRef.current = voiceOn; }, [voiceOn]);

  const getActive = useCallback((idx, data) => {
    while (idx < flow.length) {
      if (flow[idx].c && !flow[idx].c(data)) { idx++; continue; }
      return idx;
    }
    return flow.length;
  }, [flow]);

  const activeIdx = getActive(step, resp);
  const curStep = activeIdx < flow.length ? flow[activeIdx] : null;
  const progress = flow.length ? Math.min((activeIdx / flow.length) * 100, 100) : 0;

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [chat]);

  const stopListening = useCallback(() => {
    try { recRef.current?.abort(); } catch (e) {}
    try { recRef.current?.stop(); } catch (e) {}
    recRef.current = null;
    setIsListening(false);
    setInterim("");
  }, []);

  // doSubmit reads from refs so it always has current state
  const doSubmit = useCallback(async (value) => {
    if (!value || busyRef.current) return;
    clearTimeout(timerRef.current);
    pendingRef.current = "";
    stopListening();
    setInput("");
    setInterim("");

    const currentStep = stepRef.current;
    const currentResp = respRef.current;
    const idx = getActive(currentStep, currentResp);
    if (idx >= flow.length) return;

    const newResp = { ...currentResp, [flow[idx].f]: value };
    setResp(newResp);
    respRef.current = newResp;
    setChat((prev) => [...prev, { role: "user", text: value, id: Date.now() + Math.random() }]);

    const next = getActive(idx + 1, newResp);
    if (next >= flow.length) {
      const closing = "That is everything I need! Let me put your summary together. Thank you for your patience!";
      setChat((prev) => [...prev, { role: "ai", text: closing, id: Date.now() + Math.random() }]);
      busyRef.current = true;
      setIsSpeaking(true);
      await speakEL(closing);
      setIsSpeaking(false);
      busyRef.current = false;
      setScreen("summary");
    } else {
      const msg = ack() + " " + flow[next].q;
      setChat((prev) => [...prev, { role: "ai", text: msg, id: Date.now() + Math.random() }]);
      setStep(next);
      stepRef.current = next;
      if (voiceOnRef.current) {
        busyRef.current = true;
        setIsSpeaking(true);
        await speakEL(msg);
        setIsSpeaking(false);
        busyRef.current = false;
        setTimeout(() => {
          if (voiceOnRef.current && !busyRef.current) startListening();
        }, 300);
      }
    }
  }, [flow, getActive, stopListening]);

  const startListening = useCallback(() => {
    if (busyRef.current) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    stopListening();
    pendingRef.current = "";

    const r = new SR();
    r.continuous = false;
    r.interimResults = true;
    r.lang = "en-US";

    r.onstart = () => setIsListening(true);

    r.onresult = (e) => {
      let finalText = "";
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript;
        else interimText += e.results[i][0].transcript;
      }
      if (finalText) {
        const combined = pendingRef.current ? pendingRef.current + " " + finalText : finalText;
        pendingRef.current = combined;
        setInput(combined);
        setInterim("");
        // Auto-submit after 1.4s of silence
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => {
          if (pendingRef.current.trim() && !busyRef.current) {
            const toSubmit = pendingRef.current.trim();
            pendingRef.current = "";
            doSubmit(toSubmit);
          }
        }, 1400);
      } else {
        setInterim(interimText);
      }
    };

    r.onerror = () => { stopListening(); };

    // KEY FIX: When recognition ends naturally, auto-submit whatever we have
    r.onend = () => {
      setIsListening(false);
      setInterim("");
      if (pendingRef.current.trim() && !busyRef.current) {
        clearTimeout(timerRef.current);
        const toSubmit = pendingRef.current.trim();
        pendingRef.current = "";
        setTimeout(() => doSubmit(toSubmit), 200);
      }
    };

    recRef.current = r;
    r.start();
  }, [stopListening, doSubmit]);

  const beginIntake = async (t) => {
    setType(t);
    setStep(0);
    stepRef.current = 0;
    setResp({});
    respRef.current = {};
    setChat([]);
    setInput("");
    setScreen("intake");

    const f = FLOWS[t];
    const greet = t === "new"
      ? "Hi there! Welcome to Global Neuro and Spine Institute. I will help you complete your intake. It takes about 5 minutes and is much easier than paperwork."
      : "Welcome back to Global Neuro and Spine Institute! Let me quickly update your information.";

    setChat([
      { role: "ai", text: greet, id: 1 },
      { role: "ai", text: f[0].q, id: 2 },
    ]);

    busyRef.current = true;
    setIsSpeaking(true);
    await speakEL(greet);
    await speakEL(f[0].q);
    setIsSpeaking(false);
    busyRef.current = false;
    setTimeout(() => startListening(), 300);
  };

  const handleSubmit = () => {
    if (!input.trim()) return;
    doSubmit(input.trim());
  };

  const c = {
    bg: "#070B14", card: "#0F1623", border: "#1A2438",
    pri: "#3B82F6", priG: "rgba(59,130,246,.12)",
    sec: "#10B981", txt: "#E8EDF5", mut: "#8896AB", dim: "#5A6A80",
    red: "#EF4444", acc: "#F59E0B", surf: "#162032",
    aiBg: "#0D1825", userBg: "#142847",
  };

  // ── HOME SCREEN ──
  if (screen === "home") {
    return (
      <div style={{ minHeight: "100vh", background: c.bg, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 20, fontFamily: "system-ui,-apple-system,sans-serif", color: c.txt }}>
        <div style={{ textAlign: "center", maxWidth: 520 }}>
          <div style={{ width: 72, height: 72, borderRadius: 18, background: "linear-gradient(135deg,#3B82F6,#10B981)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px" }}>
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
          </div>
          <h1 style={{ fontSize: 42, fontWeight: 700, margin: 0 }}>VoiceIntake</h1>
          <p style={{ fontSize: 16, color: c.mut, margin: "8px 0 4px" }}>AI-Powered Patient Intake</p>
          <p style={{ fontSize: 13, color: c.dim, margin: "0 0 36px", lineHeight: 1.5 }}>Complete your medical intake by having a conversation. No paperwork. No typing. Just talk.</p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <button onClick={() => beginIntake("new")} style={{ padding: "16px 32px", fontSize: 15, fontWeight: 600, background: "linear-gradient(135deg,#3B82F6,#2563EB)", color: "#fff", border: "none", borderRadius: 12, cursor: "pointer", fontFamily: "inherit" }}>New Patient Intake</button>
            <button onClick={() => beginIntake("followup")} style={{ padding: "16px 32px", fontSize: 15, fontWeight: 600, background: c.surf, color: c.txt, border: "1px solid " + c.border, borderRadius: 12, cursor: "pointer", fontFamily: "inherit" }}>Follow-Up Visit</button>
          </div>
          <div style={{ marginTop: 40, padding: "10px 18px", background: c.card, borderRadius: 10, border: "1px solid " + c.border, display: "inline-block", fontSize: 12 }}>
            <span style={{ color: c.dim }}>Configured for</span>
            <span style={{ fontWeight: 600, marginLeft: 6 }}>{PRACTICE}</span>
          </div>
        </div>
      </div>
    );
  }

  // ── INTAKE SCREEN ──
  if (screen === "intake") {
    return (
      <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: c.bg, fontFamily: "system-ui,-apple-system,sans-serif", color: c.txt }}>
        {/* Header */}
        <div style={{ padding: "10px 16px", background: c.card, borderBottom: "1px solid " + c.border, display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button onClick={() => { window.speechSynthesis?.cancel(); stopListening(); setScreen("home"); }} style={{ background: "none", border: "none", color: c.mut, cursor: "pointer", fontSize: 20, padding: 2 }}>&#8592;</button>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{type === "new" ? "New Patient" : "Follow-Up"} Intake</div>
              <div style={{ fontSize: 10, color: c.dim }}>GNSI</div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button onClick={() => { const nv = !voiceOn; setVoiceOn(nv); voiceOnRef.current = nv; if (!nv) { window.speechSynthesis?.cancel(); stopListening(); } }} style={{ padding: "4px 10px", fontSize: 11, borderRadius: 6, border: "1px solid " + (voiceOn ? c.pri : c.border), background: voiceOn ? c.priG : "transparent", color: voiceOn ? c.pri : c.dim, cursor: "pointer" }}>{voiceOn ? "Sound On" : "Sound Off"}</button>
            <span style={{ fontSize: 12, color: c.dim }}>{Math.min(activeIdx + 1, flow.length)}/{flow.length}</span>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ height: 3, background: c.surf, flexShrink: 0 }}>
          <div style={{ height: "100%", width: progress + "%", background: "linear-gradient(90deg,#3B82F6,#10B981)", transition: "width .5s", borderRadius: "0 2px 2px 0" }} />
        </div>

        {/* Section label */}
        {curStep && <div style={{ padding: "6px 16px", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: c.pri, background: c.priG, flexShrink: 0 }}>{curStep.s}</div>}

        {/* Chat messages */}
        <div ref={chatRef} style={{ flex: 1, overflow: "auto", padding: "12px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
          {chat.map((m) => (
            <div key={m.id} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
              <div style={{ maxWidth: "85%", padding: "10px 14px", fontSize: 14, lineHeight: 1.5, background: m.role === "user" ? c.userBg : c.aiBg, border: "1px solid " + (m.role === "user" ? "rgba(59,130,246,.15)" : c.border), borderRadius: m.role === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px" }}>{m.text}</div>
            </div>
          ))}
          {isListening && (interim || input) && (
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <div style={{ padding: "8px 14px", borderRadius: 14, background: "rgba(239,68,68,.08)", border: "1px solid rgba(239,68,68,.15)", fontSize: 13, color: c.red, fontStyle: "italic" }}>
                {input}{interim && <span style={{ opacity: 0.6 }}> {interim}</span>}
              </div>
            </div>
          )}
        </div>

        {/* Status indicators */}
        {isSpeaking && <div style={{ padding: "6px 16px", background: "rgba(59,130,246,.04)", flexShrink: 0 }}><span style={{ fontSize: 11, color: c.pri }}>Speaking...</span></div>}
        {isListening && !isSpeaking && <div style={{ padding: "6px 16px", background: "rgba(239,68,68,.04)", flexShrink: 0 }}><span style={{ fontSize: 11, color: c.red }}>Listening... speak your answer</span></div>}

        {/* Quick-tap buttons for yes/no, choices, pain scale */}
        {curStep && (curStep.t === "yn" || curStep.t === "choice" || curStep.t === "scale") && (
          <div style={{ padding: "8px 16px", display: "flex", gap: 6, flexWrap: "wrap", flexShrink: 0, borderTop: "1px solid " + c.border, background: c.card }}>
            {curStep.t === "yn" && ["Yes", "No"].map((o) => <button key={o} onClick={() => doSubmit(o)} style={{ padding: "9px 22px", borderRadius: 8, border: "1px solid " + c.border, background: c.surf, color: c.txt, fontSize: 13, fontWeight: 500, cursor: "pointer" }}>{o}</button>)}
            {curStep.t === "choice" && curStep.o.map((o) => <button key={o} onClick={() => doSubmit(o)} style={{ padding: "9px 18px", borderRadius: 8, border: "1px solid " + c.border, background: c.surf, color: c.txt, fontSize: 13, cursor: "pointer" }}>{o}</button>)}
            {curStep.t === "scale" && <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>{Array.from({ length: 11 }, (_, n) => <button key={n} onClick={() => doSubmit(String(n))} style={{ width: 38, height: 38, borderRadius: 8, border: "1px solid " + c.border, background: n <= 3 ? "rgba(16,185,129,.08)" : n <= 6 ? "rgba(245,158,11,.08)" : "rgba(239,68,68,.08)", color: n <= 3 ? c.sec : n <= 6 ? c.acc : c.red, fontSize: 14, fontWeight: 600, cursor: "pointer" }}>{n}</button>)}</div>}
          </div>
        )}

        {/* Input bar */}
        <div style={{ padding: "10px 16px 16px", background: c.card, borderTop: "1px solid " + c.border, flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={() => { if (isListening) stopListening(); else startListening(); }} disabled={isSpeaking} style={{ width: 48, height: 48, borderRadius: "50%", border: "none", background: isListening ? "linear-gradient(135deg,#EF4444,#DC2626)" : "linear-gradient(135deg,#3B82F6,#2563EB)", color: "#fff", cursor: isSpeaking ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, opacity: isSpeaking ? 0.4 : 1 }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
            </button>
            <input type="text" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === "Enter" && handleSubmit()} placeholder={isListening ? "Listening..." : "Type or tap mic..."} style={{ flex: 1, padding: "12px 16px", fontSize: 14, background: c.surf, color: c.txt, border: "1px solid " + c.border, borderRadius: 12, outline: "none", fontFamily: "inherit" }} />
            <button onClick={handleSubmit} style={{ width: 44, height: 44, borderRadius: 12, border: "none", background: input.trim() ? "linear-gradient(135deg,#10B981,#059669)" : c.surf, color: input.trim() ? "#fff" : c.dim, cursor: input.trim() ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── SUMMARY SCREEN ──
  if (screen === "summary") {
    const groups = {};
    flow.forEach((st) => {
      if (resp[st.f]) {
        if (!groups[st.s]) groups[st.s] = [];
        groups[st.s].push({ f: st.f, a: resp[st.f] });
      }
    });

    return (
      <div style={{ minHeight: "100vh", background: c.bg, fontFamily: "system-ui,-apple-system,sans-serif", color: c.txt }}>
        <div style={{ padding: "20px 16px", background: c.card, borderBottom: "1px solid " + c.border }}>
          <div style={{ maxWidth: 640, margin: "0 auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10 }}>
              <div>
                <div style={{ fontSize: 20, fontWeight: 700 }}>{type === "new" ? "New Patient" : "Follow-Up"} Intake Summary</div>
                <div style={{ fontSize: 12, color: c.dim, marginTop: 3 }}>{PRACTICE}</div>
              </div>
              <button onClick={() => setScreen("home")} style={{ padding: "8px 16px", fontSize: 12, fontWeight: 600, background: c.surf, color: c.txt, border: "1px solid " + c.border, borderRadius: 8, cursor: "pointer" }}>New Intake</button>
            </div>
            {resp.full_name && (
              <div style={{ marginTop: 14, padding: "10px 14px", background: c.priG, borderRadius: 8, border: "1px solid rgba(59,130,246,.15)" }}>
                <span style={{ fontSize: 12, color: c.dim }}>Patient:</span>
                <span style={{ fontSize: 15, fontWeight: 600, marginLeft: 6 }}>{resp.full_name}</span>
                {resp.dob && <><span style={{ fontSize: 12, color: c.dim, marginLeft: 14 }}>DOB:</span><span style={{ fontSize: 13, marginLeft: 6 }}>{resp.dob}</span></>}
              </div>
            )}
          </div>
        </div>
        <div style={{ maxWidth: 640, margin: "0 auto", padding: "20px 16px 48px" }}>
          {Object.entries(groups).map(([sec, items]) => (
            <div key={sec} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".08em", color: c.pri, marginBottom: 10, paddingBottom: 6, borderBottom: "1px solid " + c.border }}>{sec}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {items.map((i) => (
                  <div key={i.f} style={{ padding: "8px 12px", background: c.card, borderRadius: 8, border: "1px solid " + c.border }}>
                    <div style={{ fontSize: 10, color: c.dim, marginBottom: 3, textTransform: "capitalize" }}>{i.f.replace(/_/g, " ")}</div>
                    <div style={{ fontSize: 14, lineHeight: 1.4 }}>{i.a}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div style={{ marginTop: 28, padding: "18px 20px", background: "linear-gradient(135deg,rgba(16,185,129,.08),rgba(16,185,129,.03))", borderRadius: 12, border: "1px solid rgba(16,185,129,.15)", textAlign: "center" }}>
            <div style={{ fontSize: 28, marginBottom: 6 }}>&#10003;</div>
            <div style={{ fontSize: 15, fontWeight: 600, color: c.sec }}>Intake Complete</div>
            <div style={{ fontSize: 12, color: c.mut, marginTop: 3 }}>Ready to deliver as a structured PDF via secure email.</div>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
