"use client";
import { useState, useRef, useEffect, useCallback } from "react";
const FL = {
new: [
  { s:"Demographics",q:"Let us start with your full name, first and last please.",f:"full_name",t:"text" },
  { s:"Demographics",q:"Could you spell your last name for me?",f:"last_name_spell",t:"text" },
  { s:"Demographics",q:"What is your date of birth?",f:"dob",t:"text" },
  { s:"Demographics",q:"Your height?",f:"height",t:"text" },
  { s:"Demographics",q:"And your current weight?",f:"weight",t:"text" },
  { s:"Pain History",q:"Tell me in your own words, what is the main reason you are coming in today?",f:"chief_complaint",t:"text" },
  { s:"Pain History",q:"Do you know what caused this pain? A car accident, a fall, or something else?",f:"cause",t:"text" },
  { s:"Pain History",q:"When did this happen, do you remember the approximate date?",f:"accident_date",t:"text" },
  { s:"Pain History",q:"Did you have any pain in that area before this happened?",f:"prior_pain",t:"yn" },
  { s:"Pain History",q:"Where exactly is your pain located?",f:"pain_loc",t:"text" },
  { s:"Pain History",q:"Does the pain travel or radiate anywhere, like down your arm or leg?",f:"pain_rad",t:"text" },
  { s:"Pain History",q:"What makes your pain worse?",f:"pain_worse",t:"text" },
  { s:"Pain History",q:"What helps make it better?",f:"pain_better",t:"text" },
  { s:"Pain History",q:"How would you describe your pain: sharp, burning, shooting, achy, pressure, or something else?",f:"pain_desc",t:"text" },
  { s:"Pain History",q:"On a scale of 0 to 10, how would you rate your pain right now?",f:"pain_sev",t:"scale" },
  { s:"Treatment",q:"What treatments have you tried so far: therapy, injections, medications, or surgery?",f:"treatments",t:"text" },
  { s:"Treatment",q:"What medications are you currently taking?",f:"meds",t:"text" },
  { s:"Treatment",q:"Do you have any allergies to medications or other substances?",f:"allergies",t:"text" },
  { s:"Medical History",q:"Do you have any medical conditions: diabetes, high blood pressure, heart disease, or anything else?",f:"conditions",t:"text" },
  { s:"Medical History",q:"Have you had any surgeries?",f:"surgeries",t:"text" },
  { s:"Medical History",q:"Any hospitalizations?",f:"hosps",t:"text" },
  { s:"Family History",q:"Family history of cancer, diabetes, heart disease, or stroke?",f:"fam_hx",t:"text" },
  { s:"Social History",q:"What is your marital status?",f:"marital",t:"choice",o:["Married","Single","Divorced","Separated"] },
  { s:"Social History",q:"Are you currently employed? What do you do?",f:"employment",t:"text" },
  { s:"Social History",q:"Do you smoke or use tobacco?",f:"smoking",t:"yn" },
  { s:"Social History",q:"How many packs per day, and for how many years?",f:"smoke_detail",t:"text",c:(d)=>d.smoking==="Yes" },
  { s:"Social History",q:"Do you drink alcohol?",f:"alcohol",t:"yn" },
  { s:"Social History",q:"How much and how often?",f:"alc_detail",t:"text",c:(d)=>d.alcohol==="Yes" },
  { s:"Social History",q:"Are you applying for disability?",f:"disability",t:"yn" },
  { s:"Review of Systems",q:"Quick symptom check. Any recent weight changes, weakness, fatigue, or fever?",f:"ros_const",t:"text" },
  { s:"Review of Systems",q:"Any chest pain, shortness of breath, or palpitations?",f:"ros_cardio",t:"text" },
  { s:"Review of Systems",q:"Any numbness, tingling, headaches, or memory issues?",f:"ros_neuro",t:"text" },
  { s:"Review of Systems",q:"Any other joint pain, stiffness, or loss of range of motion?",f:"ros_msk",t:"text" },
  { s:"Review of Systems",q:"How about your mood. Any anxiety, depression, or mood changes?",f:"ros_psych",t:"text" },
  { s:"Review of Systems",q:"Any other symptoms: vision, hearing, breathing, stomach, or skin?",f:"ros_other",t:"text" },
  { s:"Safety",q:"Is there any chance you could be pregnant?",f:"pregnant",t:"text" },
  { s:"Consent",q:"Last step. By completing this intake you authorize your provider to release medical information to process your insurance claims. Do you understand and agree?",f:"consent",t:"yn" }
],
followup: [
  { s:"Identification",q:"Welcome back! Can I get your full name?",f:"full_name",t:"text" },
  { s:"Current Visit",q:"What is bringing you in today?",f:"chief_complaint",t:"text" },
  { s:"Current Visit",q:"Where is your pain located?",f:"pain_loc",t:"text" },
  { s:"Current Visit",q:"What makes it worse?",f:"pain_worse",t:"text" },
  { s:"Current Visit",q:"What makes it better?",f:"pain_better",t:"text" },
  { s:"Current Visit",q:"How would you describe the pain?",f:"pain_desc",t:"text" },
  { s:"Current Visit",q:"On a scale of 0 to 10, how severe is it right now?",f:"pain_sev",t:"scale" },
  { s:"Last Visit",q:"Did you have a procedure during your last visit?",f:"had_proc",t:"yn" },
  { s:"Last Visit",q:"How much relief did the procedure give you?",f:"proc_relief",t:"choice",o:["Less than 25%","25-50%","50-75%","More than 75%"],c:(d)=>d.had_proc==="Yes" },
  { s:"Changes",q:"Any new medications since your last visit?",f:"new_meds",t:"text" },
  { s:"Changes",q:"Any new illnesses, injuries, surgeries, or hospitalizations?",f:"new_cond",t:"text" },
  { s:"Changes",q:"Any changes to your family medical history?",f:"fam_chg",t:"text" },
  { s:"Changes",q:"Changes in marital status, employment, or substance use?",f:"soc_chg",t:"text" },
  { s:"Changes",q:"Are you applying for disability?",f:"disability",t:"yn" },
  { s:"Review of Systems",q:"Any new symptoms: heart, breathing, stomach, vision, mood, numbness, or tingling?",f:"ros",t:"text" },
  { s:"Review of Systems",q:"Anything else you want the doctor to know?",f:"ros_other",t:"text" }
]
};
var ttsAudioRef = null;
async function speakEL(t) {
  try {
    const r = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: t }) });
    if (!r.ok) throw new Error("TTS failed");
    const b = await r.blob(), u = URL.createObjectURL(b);
    return new Promise((v) => {
      const a = new Audio(u);
      ttsAudioRef = a;
      a.onended = () => { URL.revokeObjectURL(u); ttsAudioRef = null; v(); };
      a.onerror = () => { URL.revokeObjectURL(u); ttsAudioRef = null; v(); };
      a.play().catch(() => { ttsAudioRef = null; v(); });
    });
  } catch (e) {
    return new Promise((v) => {
      if (!window.speechSynthesis) { v(); return; }
      const u = new SpeechSynthesisUtterance(t);
      u.rate = 0.95; u.onend = v; u.onerror = v;
      window.speechSynthesis.speak(u);
    });
  }
}
function cancelSpeech() {
  try { window.speechSynthesis?.cancel(); } catch(e) {}
  try { if (ttsAudioRef) { ttsAudioRef.pause(); ttsAudioRef.currentTime = 0; ttsAudioRef = null; } } catch(e) {}
  try { document.querySelectorAll("audio").forEach(function(a) { a.pause(); a.currentTime = 0; }); } catch(e) {}
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
  const [isThinking, setIsThinking] = useState(false);
  const chatRef = useRef(null);
  const recRef = useRef(null);
  const timerRef = useRef(null);
  const busyRef = useRef(false);
  const pendingRef = useRef("");
  const stepRef = useRef(0);
  const respRef = useRef({});
  const voiceOnRef = useRef(true);
  const doSubmitRef = useRef(null);
  const startLRef = useRef(null);
  const chatRef2 = useRef([]);
  const speakingRef = useRef(false);
  const flow = type ? FL[type] : [];
  useEffect(() => { stepRef.current = step; }, [step]);
  useEffect(() => { respRef.current = resp; }, [resp]);
  useEffect(() => { voiceOnRef.current = voiceOn; }, [voiceOn]);
  useEffect(() => { speakingRef.current = isSpeaking; }, [isSpeaking]);
  const getActive = useCallback((i, d) => {
    while (i < flow.length) { if (flow[i].c && !flow[i].c(d)) { i++; continue; } return i; }
    return flow.length;
  }, [flow]);
  const ai = getActive(step, resp);
  const cur = ai < flow.length ? flow[ai] : null;
  const prog = flow.length ? Math.min((ai / flow.length) * 100, 100) : 0;
  useEffect(() => {
    setTimeout(function() { chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" }); }, 50);
  }, [chat, isThinking, isSpeaking, isListening, interim]);
  const stopL = useCallback(() => {
    try { recRef.current?.abort(); } catch (e) {}
    try { recRef.current?.stop(); } catch (e) {}
    recRef.current = null; setIsListening(false); setInterim("");
  }, []);
  const findFieldIndex = useCallback((fieldName) => { return flow.findIndex((q) => q.f === fieldName); }, [flow]);
  const doSubmit = useCallback(async (v) => {
    if (!v) return;
    if (busyRef.current || speakingRef.current) { cancelSpeech(); busyRef.current = false; setIsSpeaking(false); speakingRef.current = false; }
    clearTimeout(timerRef.current); pendingRef.current = ""; stopL(); setInput(""); setInterim("");
    const cs = stepRef.current; const cr = respRef.current;
    const idx = getActive(cs, cr);
    if (idx >= flow.length) return;
    setChat((p) => [...p, { role: "user", text: v, id: Date.now() + Math.random() }]);
    chatRef2.current = [...chatRef2.current, { role: "user", text: v }];
    var remainingQs = [];
    for (var qi = idx; qi < flow.length; qi++) { if (!flow[qi].c || flow[qi].c(cr)) { remainingQs.push({ f: flow[qi].f, q: flow[qi].q }); } }
    setIsThinking(true); busyRef.current = true;
    try {
      const aiRes = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: v, currentQuestion: flow[idx].q, currentField: flow[idx].f, allResponses: cr, chatHistory: chatRef2.current.slice(-12), flowQuestions: remainingQs })
      });
      if (!aiRes.ok) throw new Error("AI failed");
      const aiData = await aiRes.json();
      if (aiData.error) throw new Error(aiData.error);
      setIsThinking(false);
      var newResp = { ...cr };
      if (aiData.updates) { Object.keys(aiData.updates).forEach(function(k) { newResp[k] = aiData.updates[k]; }); }
      setResp(newResp); respRef.current = newResp;
      var reply = aiData.reply || "Got it.";
      setChat((p) => [...p, { role: "ai", text: reply, id: Date.now() + Math.random() }]);
      chatRef2.current = [...chatRef2.current, { role: "ai", text: reply }];
      if (aiData.action === "stay") {
        if (voiceOnRef.current) { setIsSpeaking(true); speakingRef.current = true; await speakEL(reply); setIsSpeaking(false); speakingRef.current = false; }
        busyRef.current = false;
        setTimeout(() => { if (voiceOnRef.current && !busyRef.current && startLRef.current) startLRef.current(); }, 100);
        return;
      }
      var nextIdx = idx;
      if (aiData.skipTo) { var fi = findFieldIndex(aiData.skipTo); if (fi >= 0) nextIdx = fi; else nextIdx = getActive(idx + 1, newResp); }
      else { nextIdx = getActive(idx + 1, newResp); }
      if (nextIdx >= flow.length) {
        var cl = "That is everything I need! Let me put your summary together. Thank you for your patience!";
        setChat((p) => [...p, { role: "ai", text: cl, id: Date.now() + Math.random() }]);
        if (voiceOnRef.current) { setIsSpeaking(true); speakingRef.current = true; await speakEL(reply); await speakEL(cl); setIsSpeaking(false); speakingRef.current = false; }
        busyRef.current = false; setScreen("summary");
      } else {
        setStep(nextIdx); stepRef.current = nextIdx;
        if (voiceOnRef.current) { setIsSpeaking(true); speakingRef.current = true; await speakEL(reply); setIsSpeaking(false); speakingRef.current = false; }
        busyRef.current = false;
        setTimeout(() => { if (voiceOnRef.current && !busyRef.current && startLRef.current) startLRef.current(); }, 100);
      }
    } catch (err) {
      setIsThinking(false); console.error("AI error fallback:", err);
      var nr = { ...cr, [flow[idx].f]: v }; setResp(nr); respRef.current = nr;
      var nx = getActive(idx + 1, nr);
      if (nx >= flow.length) {
        var clFb = "That is everything! Thank you!";
        setChat((p) => [...p, { role: "ai", text: clFb, id: Date.now() + Math.random() }]);
        if (voiceOnRef.current) { setIsSpeaking(true); await speakEL(clFb); setIsSpeaking(false); }
        busyRef.current = false; setScreen("summary");
      } else {
        var m = "Got it. " + flow[nx].q;
        setChat((p) => [...p, { role: "ai", text: m, id: Date.now() + Math.random() }]);
        setStep(nx); stepRef.current = nx;
        if (voiceOnRef.current) { setIsSpeaking(true); await speakEL(m); setIsSpeaking(false); }
        busyRef.current = false;
        setTimeout(() => { if (voiceOnRef.current && !busyRef.current && startLRef.current) startLRef.current(); }, 100);
      }
    }
  }, [flow, getActive, stopL, findFieldIndex]);
  useEffect(() => { doSubmitRef.current = doSubmit; }, [doSubmit]);
  const startL = useCallback(() => {
    if (speakingRef.current || busyRef.current) { cancelSpeech(); busyRef.current = false; setIsSpeaking(false); speakingRef.current = false; }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    stopL(); pendingRef.current = "";
    const r = new SR(); r.continuous = true; r.interimResults = true; r.lang = "en-US";
    r.onstart = () => setIsListening(true);
    r.onresult = (e) => {
      let f = "", n = "";
      for (let i = e.resultIndex; i < e.results.length; i++) { if (e.results[i].isFinal) f += e.results[i][0].transcript; else n += e.results[i][0].transcript; }
      if (f) {
        const val = pendingRef.current ? pendingRef.current + " " + f : f;
        pendingRef.current = val; setInput(val); setInterim("");
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => { if (pendingRef.current.trim() && !busyRef.current) { const s = pendingRef.current.trim(); pendingRef.current = ""; if (doSubmitRef.current) doSubmitRef.current(s); } }, 1800);
      } else setInterim(n);
    };
    r.onerror = () => stopL();
    r.onend = () => { setIsListening(false); setInterim(""); if (pendingRef.current.trim() && !busyRef.current) { clearTimeout(timerRef.current); const s = pendingRef.current.trim(); pendingRef.current = ""; setTimeout(() => { if (doSubmitRef.current) doSubmitRef.current(s); }, 100); } };
    recRef.current = r; r.start();
  }, [stopL]);
  useEffect(() => { startLRef.current = startL; }, [startL]);
  const beginIntake = async (t) => {
    setType(t); setStep(0); stepRef.current = 0; setResp({}); respRef.current = {}; setChat([]); chatRef2.current = []; setInput(""); setScreen("intake");
    const f = FL[t];
    const g = t === "new" ? "Hi there! Welcome. I will help you complete your intake. Just speak naturally, and if I get anything wrong, just let me know. Let us start with your full name, first and last please." : "Welcome back to ! Let me quickly update your information. Just speak naturally. Can I get your full name?";
    setChat([{ role: "ai", text: g, id: 1 }]); chatRef2.current = [{ role: "ai", text: g }];
    busyRef.current = true; setIsSpeaking(true); speakingRef.current = true;
    await speakEL(g);
    setIsSpeaking(false); speakingRef.current = false; busyRef.current = false;
    setTimeout(() => { if (startLRef.current) startLRef.current(); }, 100);
  };
  const handleSubmit = () => { if (!input.trim()) return; doSubmit(input.trim()); };
  const MicIcon = (props) => (
    <svg width={props.size||20} height={props.size||20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
      <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
      <line x1="12" y1="19" x2="12" y2="23"/>
      <line x1="8" y1="23" x2="16" y2="23"/>
    </svg>
  );
  if (screen === "home") return (
    <div style={{minHeight:"100vh",position:"relative",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",padding:"48px 24px",overflow:"hidden"}}>
      <div className="vi-bg" />
      <div className="vi-grid" />
      <div className="vi-fade-in" style={{position:"relative",zIndex:1,textAlign:"center",maxWidth:560}}>
        <div style={{position:"relative",width:96,height:96,margin:"0 auto 32px"}}>
          <div style={{position:"absolute",inset:-18,borderRadius:36,background:"radial-gradient(circle at 30% 25%, rgba(91,141,239,0.55), transparent 65%)",filter:"blur(22px)"}}/>
          <div style={{position:"relative",width:96,height:96,borderRadius:26,background:"linear-gradient(135deg,#5B8DEF 0%,#3B82F6 50%,#10B981 100%)",display:"flex",alignItems:"center",justifyContent:"center",boxShadow:"0 22px 50px -20px rgba(91,141,239,0.7), inset 0 1px 0 rgba(255,255,255,0.3)"}}>
            <MicIcon size={42} />
          </div>
        </div>
        <h1 className="vi-headline">VoiceIntake</h1>
        <p style={{fontSize:17,color:"var(--mut)",margin:"16px 0 8px",fontWeight:500,letterSpacing:"-0.01em"}}>AI-Powered Patient Intake</p>
        <p style={{fontSize:14,color:"var(--dim)",margin:"0 auto 40px",lineHeight:1.65,maxWidth:440}}>Complete your medical intake by having a natural conversation. Correct me anytime — no paperwork needed.</p>
        <div style={{display:"flex",gap:12,justifyContent:"center",flexWrap:"wrap"}}>
          <button className="vi-btn-primary" onClick={()=>beginIntake("new")}>
            <span style={{display:"inline-flex",alignItems:"center",gap:10}}>
              <span style={{display:"inline-flex",width:18,height:18,alignItems:"center",justifyContent:"center"}}><MicIcon size={16}/></span>
              New Patient Intake
            </span>
          </button>
          <button className="vi-btn-secondary" onClick={()=>beginIntake("followup")}>Follow-Up Visit</button>
        </div>
        <div style={{marginTop:44,display:"flex",justifyContent:"center",gap:10,flexWrap:"wrap"}}>
          <span className="vi-chip"><span className="vi-chip-dot"/>HIPAA-aware</span>
          <span className="vi-chip">~3 minutes</span>
          <span className="vi-chip">Voice or text</span>
        </div>
      </div>
    </div>
  );
  if (screen === "intake") return (
    <div style={{minHeight:"100vh",display:"flex",flexDirection:"column",position:"relative"}}>
      <div className="vi-bg" />
      <header style={{position:"relative",zIndex:1,padding:"12px 18px",background:"rgba(11,16,32,0.72)",backdropFilter:"blur(12px)",borderBottom:"1px solid var(--border)",display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <button onClick={()=>{cancelSpeech();stopL();setScreen("home")}} className="vi-icon-btn" aria-label="Back">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
          </button>
          <div>
            <div style={{fontSize:14,fontWeight:600,letterSpacing:"-0.01em"}}>{type==="new"?"New Patient":"Follow-Up"} Intake</div>
            <div style={{fontSize:11,color:"var(--dim)",marginTop:1}}>{cur ? cur.s : "Wrapping up"}</div>
          </div>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <button onClick={()=>{const nv=!voiceOn;setVoiceOn(nv);voiceOnRef.current=nv;if(!nv){cancelSpeech();stopL()}}} className={"vi-toggle "+(voiceOn?"vi-toggle-on":"vi-toggle-off")} aria-label="Toggle sound">
            {voiceOn ? (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
            )}
            {voiceOn?"Sound on":"Sound off"}
          </button>
          <span style={{fontSize:12,color:"var(--mut)",fontVariantNumeric:"tabular-nums"}}>{Math.min(ai+1,flow.length)} <span style={{color:"var(--dim)"}}>/ {flow.length}</span></span>
        </div>
      </header>
      <div style={{position:"relative",zIndex:1,height:4,background:"rgba(255,255,255,0.04)"}}>
        <div className="vi-progress" style={{width:prog+"%"}}/>
      </div>
      <div ref={chatRef} style={{flex:1,overflow:"auto",padding:"20px 16px",display:"flex",flexDirection:"column",gap:10,position:"relative",zIndex:1}}>
        <div style={{maxWidth:720,margin:"0 auto",width:"100%",display:"flex",flexDirection:"column",gap:10}}>
          {chat.map((m)=> m.role === "user" ? (
            <div key={m.id} style={{display:"flex",justifyContent:"flex-end"}}>
              <div className="vi-bubble-user" style={{maxWidth:"82%",padding:"11px 15px",fontSize:14.5,lineHeight:1.5,color:"#fff",background:"linear-gradient(135deg,#3B82F6,#2563EB)",borderRadius:"16px 16px 4px 16px",boxShadow:"0 6px 18px -10px rgba(59,130,246,0.7)"}}>{m.text}</div>
            </div>
          ) : (
            <div key={m.id} style={{display:"flex",justifyContent:"flex-start",gap:10,alignItems:"flex-end"}}>
              <div style={{width:28,height:28,borderRadius:10,background:"linear-gradient(135deg,#5B8DEF,#10B981)",display:"flex",alignItems:"center",justifyContent:"center",flexShrink:0,boxShadow:"0 6px 18px -10px rgba(91,141,239,0.7)"}}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg>
              </div>
              <div className="vi-bubble-ai" style={{maxWidth:"82%",padding:"11px 15px",fontSize:14.5,lineHeight:1.55,color:"var(--txt)",background:"linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015))",border:"1px solid var(--border)",borderRadius:"16px 16px 16px 4px"}}>{m.text}</div>
            </div>
          ))}
          {isThinking && (
            <div style={{display:"flex",justifyContent:"flex-start",gap:10,alignItems:"flex-end"}}>
              <div style={{width:28,height:28,borderRadius:10,background:"linear-gradient(135deg,#5B8DEF,#10B981)",flexShrink:0}}/>
              <div style={{padding:"12px 16px",borderRadius:"16px 16px 16px 4px",background:"rgba(255,255,255,0.03)",border:"1px solid var(--border)",color:"var(--mut)",display:"inline-flex",alignItems:"center",gap:6}}>
                <span className="vi-dots"><span/><span/><span/></span>
              </div>
            </div>
          )}
          {isListening && (interim||input) && (
            <div style={{display:"flex",justifyContent:"flex-end"}}>
              <div style={{maxWidth:"82%",padding:"10px 14px",borderRadius:"16px 16px 4px 16px",background:"rgba(248,113,113,0.08)",border:"1px dashed rgba(248,113,113,0.35)",fontSize:14,color:"#FCA5A5",fontStyle:"italic"}}>{input}{interim && <span style={{opacity:0.55}}> {interim}</span>}</div>
            </div>
          )}
        </div>
      </div>
      {(isSpeaking || (isListening && !isSpeaking)) && (
        <div style={{position:"relative",zIndex:1,padding:"6px 16px",display:"flex",justifyContent:"center"}}>
          <span className="vi-chip" style={{color:isSpeaking?"var(--pri)":"#FCA5A5",borderColor:isSpeaking?"rgba(91,141,239,0.3)":"rgba(248,113,113,0.3)",background:isSpeaking?"rgba(91,141,239,0.08)":"rgba(248,113,113,0.08)"}}>
            <span className="vi-wave"><span/><span/><span/><span/><span/></span>
            {isSpeaking ? "Speaking · tap mic to interrupt" : "Listening · speak naturally"}
          </span>
        </div>
      )}
      {cur && (cur.t==="yn" || cur.t==="choice" || cur.t==="scale") && (
        <div style={{position:"relative",zIndex:1,padding:"10px 16px",borderTop:"1px solid var(--border)",background:"rgba(11,16,32,0.5)",backdropFilter:"blur(8px)"}}>
          <div style={{maxWidth:720,margin:"0 auto",display:"flex",gap:8,flexWrap:"wrap",justifyContent:cur.t==="scale"?"center":"flex-start"}}>
            {cur.t==="yn" && ["Yes","No"].map((o)=>(<button key={o} className="vi-quick" onClick={()=>doSubmit(o)} style={{minWidth:96}}>{o}</button>))}
            {cur.t==="choice" && cur.o.map((o)=>(<button key={o} className="vi-quick" onClick={()=>doSubmit(o)}>{o}</button>))}
            {cur.t==="scale" && Array.from({length:11},(_,n)=>(
              <button key={n} className="vi-scale" onClick={()=>doSubmit(String(n))} style={{
                border:"1px solid "+(n<=3?"rgba(16,185,129,0.4)":n<=6?"rgba(245,158,11,0.4)":"rgba(248,113,113,0.4)"),
                background:n<=3?"rgba(16,185,129,0.10)":n<=6?"rgba(245,158,11,0.10)":"rgba(248,113,113,0.10)",
                color:n<=3?"var(--sec)":n<=6?"var(--acc)":"var(--red)"
              }}>{n}</button>
            ))}
          </div>
        </div>
      )}
      <div style={{position:"relative",zIndex:1,padding:"12px 16px 18px",borderTop:"1px solid var(--border)",background:"rgba(11,16,32,0.72)",backdropFilter:"blur(12px)"}}>
        <div style={{maxWidth:720,margin:"0 auto",display:"flex",gap:10,alignItems:"center"}}>
          <div style={{position:"relative",width:52,height:52,flexShrink:0}}>
            {isListening && <span className="vi-pulse-ring" style={{position:"absolute",inset:0,borderRadius:"50%",border:"2px solid rgba(248,113,113,0.6)"}}/>}
            <button onClick={()=>{if(isListening)stopL();else startL()}} disabled={isThinking}
              className={isListening?"vi-listening-mic":(isSpeaking?"vi-speaking-mic":"")}
              style={{position:"relative",width:52,height:52,borderRadius:"50%",border:"none",cursor:isThinking?"default":"pointer",color:"#fff",display:"flex",alignItems:"center",justifyContent:"center",opacity:isThinking?0.4:1,
                background:isListening?"linear-gradient(135deg,#F87171,#DC2626)":"linear-gradient(135deg,#5B8DEF,#2563EB)",
                boxShadow:isListening?"0 10px 30px -10px rgba(239,68,68,0.6)":"0 10px 30px -10px rgba(59,130,246,0.6)"}}
              aria-label={isListening?"Stop listening":"Start listening"}>
              <MicIcon size={20} />
            </button>
          </div>
          <input type="text" value={input} onChange={(e)=>setInput(e.target.value)} onKeyDown={(e)=>e.key==="Enter"&&handleSubmit()} placeholder={isListening?"Listening...":"Type or tap the mic..."} className="vi-input"/>
          <button onClick={handleSubmit} disabled={!input.trim()} aria-label="Send"
            style={{width:48,height:48,borderRadius:14,border:"none",flexShrink:0,cursor:input.trim()?"pointer":"default",display:"flex",alignItems:"center",justifyContent:"center",transition:"transform 0.15s ease, filter 0.15s ease",
              background:input.trim()?"linear-gradient(135deg,#10B981,#059669)":"rgba(255,255,255,0.04)",
              color:input.trim()?"#fff":"var(--dim)",
              boxShadow:input.trim()?"0 10px 24px -12px rgba(16,185,129,0.7)":"none"}}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
  if (screen === "summary") {
    const g = {};
    flow.forEach((s) => { if (resp[s.f]) { if (!g[s.s]) g[s.s] = []; g[s.s].push({ f: s.f, a: resp[s.f] }); } });
    return (
      <div style={{minHeight:"100vh",position:"relative"}}>
        <div className="vi-bg" />
        <div style={{position:"relative",zIndex:1,padding:"28px 16px 22px",borderBottom:"1px solid var(--border)",background:"rgba(11,16,32,0.72)",backdropFilter:"blur(10px)"}}>
          <div style={{maxWidth:680,margin:"0 auto"}}>
            <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:6}}>
              <div style={{width:6,height:24,borderRadius:3,background:"linear-gradient(180deg,#5B8DEF,#10B981)"}}/>
              <div style={{fontSize:11,fontWeight:700,letterSpacing:"0.14em",textTransform:"uppercase",color:"var(--mut)"}}>Intake Summary</div>
            </div>
            <div style={{fontSize:26,fontWeight:700,letterSpacing:"-0.02em"}}>{type==="new"?"New Patient":"Follow-Up"} Visit</div>
            {resp.full_name && (
              <div className="vi-card" style={{marginTop:16,padding:"12px 16px",display:"flex",alignItems:"center",gap:12}}>
                <div style={{width:36,height:36,borderRadius:12,background:"linear-gradient(135deg,#5B8DEF,#10B981)",display:"flex",alignItems:"center",justifyContent:"center",fontSize:14,fontWeight:700,color:"#fff",flexShrink:0}}>
                  {(resp.full_name||"").trim().split(/\s+/).map(w=>w[0]).filter(Boolean).slice(0,2).join("").toUpperCase()}
                </div>
                <div>
                  <div style={{fontSize:11,color:"var(--dim)",textTransform:"uppercase",letterSpacing:"0.08em"}}>Patient</div>
                  <div style={{fontSize:15,fontWeight:600}}>{resp.full_name}</div>
                </div>
              </div>
            )}
            <button onClick={()=>setScreen("home")} className="vi-btn-secondary" style={{marginTop:14,padding:"10px 18px",fontSize:13,borderRadius:10}}>Start New Intake</button>
          </div>
        </div>
        <div style={{position:"relative",zIndex:1,maxWidth:680,margin:"0 auto",padding:"24px 16px 60px"}}>
          {Object.entries(g).map(([s,items])=>(
            <div key={s} style={{marginBottom:24}}>
              <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:12}}>
                <div style={{width:4,height:16,borderRadius:2,background:"var(--pri)"}}/>
                <div style={{fontSize:11,fontWeight:700,textTransform:"uppercase",letterSpacing:"0.12em",color:"var(--mut)"}}>{s}</div>
                <div style={{flex:1,height:1,background:"linear-gradient(90deg,var(--border),transparent)"}}/>
              </div>
              <div style={{display:"flex",flexDirection:"column",gap:8}}>
                {items.map((i)=>(
                  <div key={i.f} className="vi-card" style={{padding:"12px 16px"}}>
                    <div style={{fontSize:10.5,color:"var(--dim)",textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:3}}>{i.f.replace(/_/g," ")}</div>
                    <div style={{fontSize:14.5,lineHeight:1.5}}>{i.a}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div style={{marginTop:28,padding:"22px 24px",background:"linear-gradient(135deg, rgba(16,185,129,0.10), rgba(91,141,239,0.06))",borderRadius:16,border:"1px solid rgba(16,185,129,0.25)",textAlign:"center"}}>
            <div style={{width:44,height:44,borderRadius:14,background:"linear-gradient(135deg,#10B981,#059669)",display:"flex",alignItems:"center",justifyContent:"center",margin:"0 auto 12px",boxShadow:"0 14px 30px -14px rgba(16,185,129,0.6)"}}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </div>
            <div style={{fontSize:16,fontWeight:600,color:"#86EFAC"}}>Intake Complete</div>
            <div style={{fontSize:13,color:"var(--mut)",marginTop:4}}>Ready to deliver as PDF via secure email.</div>
          </div>
        </div>
      </div>
    );
  }
  return null;
}
