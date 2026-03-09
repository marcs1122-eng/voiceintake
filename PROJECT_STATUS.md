# VoiceIntake — Complete Project Status
Last Updated: March 9, 2026

## What This Product Is
AI-powered voice patient intake system. Patients call a phone number, speak to "Sarah" (AI), 
complete their full intake conversationally. Practice receives a structured PDF summary by email.
Replaces paper forms and tablet intake (Phreesia competitor).

Owner: Mac (former healthcare CEO, ~15 years experience)
Pilot target: Brother's practice — Global Neuro & Spine Institute (GNSI), Jensen Beach FL
Pricing target: $299–$799/month per practice
Go-to-market: B2B SaaS, voice-first, specialty medical practices

---

## Live Credentials & URLs

| Item | Value |
|------|-------|
| Live app | https://voiceintake.vercel.app |
| GitHub repo | https://github.com/marcs1122-eng/voiceintake |
| Vercel account | marcs1122@gmail.com (aipaper team, Pro Trial) |
| Twilio phone | +1 (772) 325-1556 |
| Twilio Account SID | ACd7f451e1fbb177da07920f3449acd330 |
| Twilio Auth Token | 481e5bef127b7d97b3278dfe40acbde1 |
| Anthropic API Key | ANTHROPIC_API_KEY env var (key name: VoiceIntake2) |
| ElevenLabs API Key | ELEVENLABS_API_KEY env var |
| ElevenLabs Voice | Grace - Customer Service Angel |
| ElevenLabs Voice ID | kSDv9EbJ41pJUICMEOOu |
| NEXT_PUBLIC_BASE_URL | https://voiceintake.vercel.app |
| Upstash Redis (KV) | voiceintake-sessions (Washington DC iad1, Free tier) |
| ElevenLabs Agent ID | agent_5701kk7t4q0bfjarqs72z9x03tyk |
| ElevenLabs Agent URL | https://elevenlabs.io/app/agents/agents/agent_5701kk7t4q0bfjarqs72z9x03tyk |
| ElevenLabs Phone Number ID | phnum_4201kk96we8aezfrv95qqhcd671t |

---

## Architecture

### Current Flow (LIVE)
Patient calls (772) 325-1556
→ Twilio routes to ElevenLabs Conversational AI (WebSocket streaming)
→ Claude Haiku 4.5 as LLM brain
→ Grace (ElevenLabs) as voice
→ ~500ms response latency
→ On call completion: POST webhook → /api/call/complete on Vercel
→ Claude parses transcript → generates PDF → Resend emails PDF to practice

### Old Flow (RETIRED - routes still exist but inactive)
Twilio → /api/call/incoming → Claude → ElevenLabs TTS → Twilio plays (had 4-6s latency)

---

## Tech Stack
- ElevenLabs Conversational AI — full voice pipeline (STT, LLM routing, TTS, WebSocket)
- Twilio — phone number only
- Claude Haiku 4.5 — LLM (via ElevenLabs integration)
- Grace (ElevenLabs) — voice
- Next.js 14 (App Router) on Vercel — web UI + API routes
- Anthropic API — direct for PDF parsing in /api/call/complete
- pdfkit — PDF generation
- Resend — transactional email
- Upstash Redis (Vercel KV) — session storage (less critical now with ElevenLabs managing state)

---

## ElevenLabs Agent Config (Current)

Agent name: Sarah - Patient Intake
Voice: Grace - Customer Service Angel (Primary)
TTS Model: V3 Conversational (Alpha)
LLM: Claude Haiku 4.5
Max tokens: 300
Language: English
Interruptible: ON

Advanced settings (tuned March 9 2026):
- Eagerness: Normal (was: Patient)
- Speculative turn: ON (was: OFF) — starts generating during user's last word, faster response
- Take turn after silence: 3 seconds (was: 7 seconds)
- Spelling patience: Auto

First message:
"Hi, thanks for calling. This is Sarah, and I'll be helping collect your intake information today. Are you a new patient or a follow-up visit?"

NOTE: All GNSI/practice-specific branding removed from agent. Uses "this medical office" generically.
Practice-specific details (address, doctors, phone/fax) are placeholder — need to be filled in for each client.

---

## System Prompt Key Rules (in agent)

1. NAME SPELLING: When patient gives name, IMMEDIATELY spell it back in same response and confirm
   Example: "Great, I have that as J-O-H-N S-M-I-T-H — is that correct?"

2. MEDICATIONS: When patient lists meds, repeat ALL back before moving on

3. ENCOURAGEMENT: After Q20 (new patient) or Q10 (follow-up):
   "Almost done, [name] — just a few more questions and we're all set."

4. CALL DROP RECOVERY: If patient says they were disconnected, get name, resume from logical point

5. WRAP-UP: After final question, ask: "Do you have any questions about the practice — like our 
   location, our doctors, or how to reach us?"

6. APPOINTMENTS: Never schedule or quote times. Always redirect:
   "I'm not able to schedule appointments directly — our staff will be in touch, or you can call 
   us during business hours."

7. INSURANCE/BILLING: Redirect to staff during business hours

---

## Question Flows

### New Patient (29 questions + wrap-up):
1. Full name → IMMEDIATELY spell back and confirm
2. DOB
3. Height
4. Weight
5. Chief complaint
6. Cause (auto accident, slip/fall, other)
7. Date of accident/injury
8. Prior pain before accident (yes/no)
9. Pain location
10. Pain radiation (arm/leg, which side)
11. Pain worse triggers
12. Pain better triggers
13. Pain description (sharp, burning, shooting, etc.)
14. Pain severity 0-10
15. Treatments tried
16. Current medications → repeat all back to confirm
17. Allergies
18. Medical conditions
19. Past surgeries
20. Past hospitalizations
★ ENCOURAGEMENT: "Almost done, [name] — just a few more questions and we're all set."
21. Family history
22. Marital status
23. Employment
24. Smoking
25. Alcohol
26. Disability (yes/no)
27. Review of systems (constitutional, cardio, neuro, MSK, psych, other)
28. Pregnant
29. Verbal consent (recorded on call)
30. WRAP-UP: Any questions about the practice?

### Follow-Up (15 questions + wrap-up):
1. Full name → IMMEDIATELY spell back and confirm
2. Chief complaint today
3. Pain location
4. Pain worse
5. Pain better
6. Pain description
7. Pain severity 0-10
8. Had procedure at last visit (yes/no)
9. If yes: how much relief (<25%, 25-50%, 50-75%, >75%)
10. New medications since last visit
★ ENCOURAGEMENT: "Almost done — just a couple more questions."
11. New illnesses/injuries/surgeries/hospitalizations
12. Family history changes
13. Social history changes
14. Disability (yes/no)
15. Review of systems (any new symptoms)
16. WRAP-UP: Any questions about the practice?

---

## File Structure (GitHub repo)

app/
  page.js                    — Web browser intake UI (secondary, phone is primary)
  layout.js                  — Root layout
  api/
    call/
      complete/route.js      — ★ NEW: Post-call webhook. Parses transcript → PDF → email via Resend
      incoming/route.js      — LEGACY: Old Twilio answer handler (inactive)
      respond/route.js       — LEGACY: Old turn processor (inactive)
      status/route.js        — Logs call completion
    chat/route.js             — Web browser AI conversation
    tts/route.js              — ElevenLabs TTS for web browser
    audio/route.js            — ElevenLabs TTS for phone (legacy)

---

## Environment Variables (Vercel)

| Variable | Status | Notes |
|----------|--------|-------|
| ANTHROPIC_API_KEY | ✅ Set | Key name: VoiceIntake2 |
| ELEVENLABS_API_KEY | ✅ Set | Working |
| NEXT_PUBLIC_BASE_URL | ✅ Set | https://voiceintake.vercel.app |
| KV_REST_API_URL | ✅ Set | Upstash Redis |
| KV_REST_API_TOKEN | ✅ Set | Upstash Redis |
| RESEND_API_KEY | ⚠️ NEEDS TO BE ADDED | Get from resend.com |
| PRACTICE_EMAIL | ⚠️ NEEDS TO BE ADDED | Email where completed intakes go |

---

## COMPLETED THIS SESSION ✅

- Migrated from custom Vercel webhook to ElevenLabs Conversational AI (fixed 4-6s latency)
- Connected Twilio (772) 325-1556 to ElevenLabs agent natively
- Removed all GNSI/practice-specific branding from agent (now generic)
- Fixed name spelling: Sarah spells back immediately in same breath (not a follow-up turn)
- Added medication confirmation: Sarah repeats all meds back before moving on
- Added "almost done" encouragement at Q20/Q10 — neutral tone, works for all ages
- Added call drop recovery logic to prompt
- Added wrap-up question at end of every call
- Added appointment deflection scripting
- Added billing/insurance deflection scripting
- Tuned Advanced settings: Eagerness=Normal, Speculative turn=ON, Silence timeout=3s
- Built /api/call/complete route: parses transcript → generates PDF via pdfkit → emails via Resend
- Updated package.json with pdfkit and resend dependencies
- Built Practice Onboarding Questionnaire (Word doc) — 6-section form for new practice meetings
- Clarified HIPAA/verbal consent strategy: Sarah handles HIPAA ack + consent to treat verbally;
  AOB/ROI/Medicare ABN need digital signature (SMS link — future build)

---

## PENDING — NOT YET BUILT ❌

### Priority 1 — Complete Before Pilot Demo
1. Add RESEND_API_KEY and PRACTICE_EMAIL to Vercel env vars
2. Set ElevenLabs post-call webhook URL to: https://voiceintake.vercel.app/api/call/complete
   (ElevenLabs agent → Analysis tab → Post-call webhook)
3. Redeploy Vercel to pick up pdfkit + resend packages
4. Fill in GNSI practice details in agent prompt (address, doctors, phone/fax)
5. Add GNSI website to ElevenLabs Knowledge Base (Knowledge Base tab → URL scrape)
6. Test full call → confirm PDF email arrives

### Priority 2 — Next Sprint
7. Session resume: save progress to DB keyed by phone number, resume if dropped
8. SMS + pre-filled e-signature link for AOB/ROI/Medicare ABN forms
9. Practice-specific onboarding: scan their forms → extract questions → build custom agent prompt

### Priority 3 — After First Customer
10. Admin dashboard: practices log in, view completed intakes, download PDFs
11. Multi-practice support: each practice gets own agent + phone number
12. BAAs: ElevenLabs Enterprise + Anthropic Enterprise before paying customers
13. Outbound calling: Sarah calls patients before appointments

---

## HIPAA Status
NOT fully compliant yet. Pilot with GNSI acceptable under informal arrangement.
Before any paying customers:
- ElevenLabs Enterprise plan (has BAA)
- Anthropic Enterprise BAA
- Twilio BAA (available on standard plan)
- Vercel is NOT HIPAA compliant — long-term, move to Railway or AWS for PHI storage
- HIPAA-compliant email for PDF delivery (Paubox or Virtru — Resend is NOT HIPAA compliant)

---

## Competitive Context
- Primary competitor: Phreesia (tablet-based intake at kiosk in office)
- Key differentiator: Voice-first, phone-based, no app/tablet/download required
- Elderly patient advantage: 80-year-old can complete intake from home by phone
- PDF-to-email delivery is sufficient for pilot; EHR integration intentionally deferred
- Verbal consent on recorded call is legally valid for HIPAA ack + consent to treat
- AOB/ROI need written signature (future SMS e-sign flow)

---

## Practice Onboarding Process (Defined)
1. Walk in with Practice Onboarding Questionnaire (Word doc — already built)
2. Collect: website URL, doctors list, address/phone/fax, specialty questions, form copies
3. Photograph their existing intake forms
4. Upload forms to Claude → extract questions → build custom agent prompt (~10 min)
5. Feed website URL to ElevenLabs Knowledge Base (auto-scrapes doctors, hours, services)
6. Demo call in front of practice manager
7. Sign BAA, go live

---

## Key Product Decisions (Do Not Re-debate)
- Phone-first, not app/tablet
- ElevenLabs Conversational AI (not custom webhook pipeline) — latency too bad otherwise
- Claude Haiku 4.5 as LLM (fast, cheap, accurate enough for intake)
- Grace voice (ElevenLabs) — warm, professional
- PDF-to-email delivery — no EHR integration at this stage
- Premium pricing $299-799/month — value is staff time saved + elderly accessibility
- Speed to market is the moat — build switching costs before big players enter
