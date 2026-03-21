import { NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';
import { kv } from '@vercel/kv';

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const BASE_URL = 'https://voiceintake.vercel.app';

const NEW_PATIENT_QUESTIONS = [
  { field: 'full_name', question: 'What is your full name?' },
  { field: 'name_spelling_first', question: 'Can you spell your first name please?' },
  { field: 'name_confirm_first', question: 'Is that spelling correct?' },
  { field: 'name_spelling_last', question: 'Now can you spell your last name please?' },
  { field: 'name_confirm_last', question: 'Is that spelling correct?' },
  { field: 'dob', question: 'What is your date of birth?' },
  { field: 'height', question: 'What is your height?' },
  { field: 'weight', question: 'What is your weight?' },
  { field: 'chief_complaint', question: 'What brings you in today?' },
  { field: 'cause', question: 'Was your pain caused by an auto accident, a slip and fall, or something else?' },
  { field: 'pain_loc', question: 'Where exactly is your pain located?' },
  { field: 'pain_rad', question: 'Does your pain travel anywhere, like down your arm or leg?' },
  { field: 'pain_worse', question: 'What makes your pain worse?' },
  { field: 'pain_better', question: 'What makes your pain better?' },
  { field: 'pain_desc', question: 'How would you describe your pain? Sharp, burning, shooting, achy, or pressure?' },
  { field: 'pain_sev', question: 'On a scale of 0 to 10, what is your pain level right now?' },
  { field: 'treatments', question: 'What treatments have you tried? Therapy, injections, medications, or surgery?' },
  { field: 'meds', question: 'What medications are you currently taking?' },
  { field: 'allergies', question: 'Any allergies to medications or other substances?' },
  { field: 'conditions', question: 'Do you have any medical conditions like diabetes, high blood pressure, heart disease, or cancer?' },
  { field: 'surgeries', question: 'Have you had any surgeries?' },
  { field: 'hosps', question: 'Any hospitalizations?' },
  { field: 'fam_hx', question: 'Any family history of cancer, diabetes, heart disease, or stroke?' },
  { field: 'marital', question: 'What is your marital status?' },
  { field: 'employment', question: 'What is your current occupation or employment status?' },
  { field: 'smoking', question: 'Do you smoke?' },
  { field: 'alcohol', question: 'Do you drink alcohol?' },
  { field: 'disability', question: 'Are you applying for disability benefits?' },
  { field: 'ros_const', question: 'Any recent weight changes, fatigue, or fever?' },
  { field: 'ros_cardio', question: 'Any chest pain, shortness of breath, or palpitations?' },
  { field: 'ros_neuro', question: 'Any numbness, tingling, weakness, or memory problems?' },
  { field: 'ros_msk', question: 'Any other joint pain or limited range of motion?' },
  { field: 'ros_psych', question: 'Any anxiety, depression, or mood changes?' },
  { field: 'ros_other', question: 'Any other symptoms you want to mention?' },
  { field: 'pregnant', question: 'Are you currently pregnant or planning to become pregnant?' },
  { field: 'consent', question: 'Last one — do you authorize Global Neuro and Spine Institute to use your information to process your claims and treatment?' },
];

const FOLLOWUP_QUESTIONS = [
  { field: 'full_name', question: 'What is your full name?' },
  { field: 'chief_complaint', question: 'What is your main complaint today?' },
  { field: 'pain_loc', question: 'Where is your pain located?' },
  { field: 'pain_worse', question: 'What makes it worse?' },
  { field: 'pain_better', question: 'What makes it better?' },
  { field: 'pain_desc', question: 'How would you describe the pain — sharp, burning, shooting, achy, or pressure?' },
  { field: 'pain_sev', question: 'Pain level 0 to 10?' },
  { field: 'had_proc', question: 'Did you have a procedure at your last visit?' },
  { field: 'proc_relief', question: 'How much relief did it give — less than 25%, 25 to 50%, 50 to 75%, or more than 75%?' },
  { field: 'new_meds', question: 'Any new medications since your last visit?' },
  { field: 'new_cond', question: 'Any new illnesses, injuries, or hospitalizations since your last visit?' },
  { field: 'fam_chg', question: 'Any changes in family history?' },
  { field: 'soc_chg', question: 'Any changes in your personal situation — job, relationships, or habits?' },
  { field: 'disability', question: 'Are you applying for disability?' },
  { field: 'ros', question: 'Any new symptoms — chest pain, shortness of breath, numbness, or tingling?' },
  { field: 'ros_other', question: 'Anything else before your appointment?' },
];

// FIX: Corrected progress messages — 8 is ~21% done (not halfway), 17 is truly ~50%, 28 is ~82%
const PROGRESS_MESSAGES = {
  8:  "You're doing great!",
  17: "You're about halfway through, doing great!",
  28: "Almost done now, just a few more.",
};

// Fire-and-forget PDF generation — never blocks the call response
async function triggerPDF(session, callDuration) {
  try {
    const transcript = session.chatHistory.map(h => ({
      role: h.role === 'assistant' ? 'agent' : 'user',
      message: h.content,
    }));
    fetch(`${BASE_URL}/api/call/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data: {
          transcript,
          conversation_id: session.callSid,
          metadata: { call_duration_secs: callDuration || 0 },
        },
      }),
    }).catch(err => console.error('[respond] PDF trigger failed:', err.message));
    console.log(`[respond] PDF triggered for ${session.callSid}`);
  } catch (err) {
    console.error('[respond] PDF trigger error:', err.message);
  }
}

export async function POST(request) {
  let formData;
  try {
    formData = await request.formData();
  } catch (e) {
    console.error('FormData parse error:', e);
    return errorTwiml();
  }

  const speechResult = (formData.get('SpeechResult') || '').trim();
  const callSid = formData.get('CallSid') || '';
  const callDuration = parseInt(formData.get('CallDuration') || '0', 10);
  const url = new URL(request.url);
  const flowType = url.searchParams.get('flow') || 'new';

  console.log(`[${callSid}] Speech: "${speechResult}"`);

  let session = await kv.get(`session:${callSid}`);
  if (!session) {
    session = { flowType, callSid, questionIndex: 0, allResponses: {}, chatHistory: [] };
  }

  const questions = session.flowType === 'followup' ? FOLLOWUP_QUESTIONS : NEW_PATIENT_QUESTIONS;
  const currentQ = questions[session.questionIndex];

  if (!speechResult) {
    kv.set(`session:${callSid}`, session, { ex: 3600 }).catch(() => {});
    const isSpellFallback = ['name_spelling_first', 'name_spelling_last'].includes(currentQ?.field);
    return respondWithAudio(`I didn't catch that. ${currentQ.question}`, flowType, false, isSpellFallback);
  }

  const goBackPhrases = ['go back', 'previous question', 'last question', 'back up', 'undo that', 'change my last'];
  if (goBackPhrases.some(p => speechResult.toLowerCase().includes(p)) && session.questionIndex > 0) {
    session.questionIndex -= 1;
    const prevQ = questions[session.questionIndex];
    kv.set(`session:${callSid}`, session, { ex: 3600 }).catch(() => {});
    return respondWithAudio(`No problem. ${prevQ.question}`, flowType);
  }

  let claudeResponse;
  try {
    claudeResponse = await processWithClaude(speechResult, session, questions);
  } catch (err) {
    console.error(`[${callSid}] Claude error:`, err);
    return respondWithAudio("Sorry about that — could you repeat your answer?", flowType);
  }

  const { action, updates, reply, skipTo } = claudeResponse;
  session.allResponses = { ...session.allResponses, ...updates };
  session.chatHistory = [
    ...session.chatHistory,
    { role: 'user', content: speechResult },
    { role: 'assistant', content: reply },
  ].slice(-12);

  if (action === 'advance') {
    if (skipTo) {
      const skipIndex = questions.findIndex(q => q.field === skipTo);
      session.questionIndex = skipIndex !== -1 ? skipIndex : session.questionIndex + 1;
    } else {
      session.questionIndex += 1;
    }
  }

  if (session.questionIndex >= questions.length) {
    kv.del(`session:${callSid}`).catch(() => {});
    console.log(`[${callSid}] Intake complete. Triggering PDF...`);
    triggerPDF(session, callDuration);
    const finalText = `${reply} Your intake is all set. The clinical team will review everything before your appointment. Thanks so much and have a great day!`;
    return respondWithAudio(finalText, flowType, true);
  }

  // FIX: Non-blocking KV save — never awaited on the hot path
  kv.set(`session:${callSid}`, session, { ex: 3600 }).catch(() => {});

  const progressMsg = PROGRESS_MESSAGES[session.questionIndex] || '';
  const fullReply = progressMsg ? `${reply} ${progressMsg}` : reply;
  // Use longer speechTimeout when asking a spelling question
  const SPELL_FIELDS = ['name_spelling_first', 'name_spelling_last'];
  const isSpellMode = SPELL_FIELDS.includes(questions[session.questionIndex]?.field);
  return respondWithAudio(fullReply, flowType, false, isSpellMode);
}

async function processWithClaude(speech, session, questions) {
  const currentQ = questions[session.questionIndex];
  const nextQ = questions[session.questionIndex + 1];
  const firstName = (session.allResponses['full_name'] || '').split(' ')[0] || '';

  const systemPrompt = `You are Sarah, a warm and caring intake assistant for Global Neuro and Spine Institute in Florida. You are on a phone call with a patient. Sound completely natural — like a real person, not a robot or a form. Think of how a great nurse talks to patients.

VOICE RULES — critical, these are spoken aloud on a phone:
1. 1-2 short sentences MAX per reply. Never longer.
2. When advancing, briefly acknowledge then ask next question — in one reply.
3. Never repeat a question already answered.
4. Use contractions: "you're", "that's", "I'll", "let's" — sounds human.
5. NO "Great!", "Certainly!", "Absolutely!", "I understand" — robotic and fake.
6. ${firstName ? `Use ${firstName}'s name occasionally, not every time.` : 'Warm friendly tone.'}
7. If patient asks something off-topic like office location or hours, answer in one brief sentence then return to the question.

MEDICAL UNDERSTANDING — interpret these patient phrasings correctly:
- "water pill" = diuretic
- "sugar" or "diabetic" = diabetes
- "bad back" = lumbar pain
- "blood thinner" = anticoagulant
- "tonsils out" or "tonsillectomy" = tonsil surgery
- "tubes in ears" = myringotomy
- "knee replaced" = total knee arthroplasty
- "nerve pain" or "burning down my leg" = neuropathic/radicular pain
- "numb fingers" = peripheral neuropathy
- Accept: "yeah", "nope", "uh huh", "nah", "not really", "kind of"

SPECIAL FIELDS:
- name_spelling_first: Patient spells their first name letter by letter. Twilio transcribes this as space-separated letters like "M a r c". Capture every letter, reconstruct the name, and read it back: "Got it — [FirstName] spelled [M-A-R-C]. Is that right?" Store as first_name_confirmed.
- name_confirm_first: Patient confirms first name spelling. Yes/correct = advance. If they say no or correct it, update first_name_confirmed with the corrected spelling, stay on name_confirm_first, read corrected spelling back to re-confirm.
- name_spelling_last: Patient spells their last name letter by letter. Same Twilio format — space-separated letters. Reconstruct and read back: "Got it — [LastName] spelled [S-L-O-B-A-S-K-Y]. Is that right?" Store as last_name_confirmed.
- name_confirm_last: Patient confirms last name spelling. Yes = advance. No/correction = update last_name_confirmed, stay, re-confirm. When advancing, also store full_name_confirmed = first_name_confirmed + " " + last_name_confirmed.
- dob: Accept any spoken format — "10 15 1980", "ten fifteen eighty", "October 15th 1980" all mean the same date. Store as MM/DD/YYYY. Never ask the patient to restate in a different format.

CURRENT STATE:
- Visit: ${session.flowType === 'followup' ? 'Follow-up' : 'New patient'}
- Field: ${currentQ?.field}
- Question: "${currentQ?.question}"
- Next: "${nextQ?.question || 'Last question — wrap up warmly.'}"
- Collected: ${Object.keys(session.allResponses).join(', ') || 'none'}
- Name: ${session.allResponses['full_name'] || 'unknown'}
- First name confirmed: ${session.allResponses['first_name_confirmed'] || 'unknown'}
- Last name confirmed: ${session.allResponses['last_name_confirmed'] || 'unknown'}

Reply ONLY with valid JSON, no markdown, no backticks:
{"action":"advance","updates":{"field":"value"},"reply":"spoken reply","skipTo":null}`;

  const response = await anthropic.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 200,
    system: systemPrompt,
    messages: [
      ...session.chatHistory.slice(-6).map(h => ({ role: h.role, content: h.content })),
      { role: 'user', content: speech },
    ],
  });

  const text = response.content[0].text.trim();
  try {
    return JSON.parse(text);
  } catch (e) {
    console.error('Claude JSON parse error:', text);
    return { action: 'stay', updates: {}, reply: "Could you say that again?", skipTo: null };
  }
}

function respondWithAudio(text, flowType, isFinal = false, spellMode = false) {
  const audioUrl = `${BASE_URL}/api/audio?text=${encodeURIComponent(text)}`;
  const actionUrl = `${BASE_URL}/api/call/respond?flow=${flowType}`;
  // Spelling questions need longer timeout — patients pause ~1s between letters
  const st = spellMode ? '3' : '1';
  let twiml;

  if (isFinal) {
    twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>${audioUrl}</Play>
</Response>`;
  } else {
    twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="${actionUrl}" method="POST"
    speechTimeout="${st}"
    speechModel="phone_call" enhanced="true" language="en-US" timeout="10">
    <Play>${audioUrl}</Play>
  </Gather>
  <Gather input="speech" action="${actionUrl}" method="POST"
    speechTimeout="${st}"
    speechModel="phone_call" enhanced="true" language="en-US" timeout="10">
    <Play>${BASE_URL}/api/audio?text=${encodeURIComponent("I didn't catch that. " + text)}</Play>
  </Gather>
  <Play>${BASE_URL}/api/audio?text=${encodeURIComponent("I'm having trouble hearing you. Please try calling back. Goodbye.")}</Play>
  <Hangup/>
</Response>`;
  }

  return new NextResponse(twiml, { headers: { 'Content-Type': 'text/xml' } });
}

function errorTwiml() {
  return new NextResponse(`<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>${AASE_URL}/api/audio?text=${encodeURIComponent("I'm sorry, something went wrong. Please call back in a moment.")}</Play>
  <Hangup/>
</Response>`, { headers: { 'Content-Type': 'text/xml' } });
}
