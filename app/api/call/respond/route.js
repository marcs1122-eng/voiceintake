import { NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const NEW_PATIENT_QUESTIONS = [
  { field: 'full_name', question: 'What is your full name?' },
  { field: 'name_spelling', question: 'Thank you! Can you spell your first and last name for me?' },
  { field: 'name_confirm', question: 'Let me make sure I have that right. I will read back your name and spelling — please confirm if it is correct or let me know any corrections.' },
  { field: 'dob', question: 'What is your date of birth?' },
  { field: 'height', question: 'What is your height?' },
  { field: 'weight', question: 'What is your weight?' },
  { field: 'chief_complaint', question: 'What brings you in today? What is your main complaint?' },
  { field: 'cause', question: 'Was your pain caused by an auto accident, a slip and fall, or something else?' },
  { field: 'pain_loc', question: 'Where exactly is your pain located?' },
  { field: 'pain_rad', question: 'Does your pain radiate or travel anywhere, like down your arm or leg?' },
  { field: 'pain_worse', question: 'What makes your pain worse?' },
  { field: 'pain_better', question: 'What makes your pain better?' },
  { field: 'pain_desc', question: 'How would you describe your pain? For example: sharp, burning, shooting, achy, pressure, or deep?' },
  { field: 'pain_sev', question: 'On a scale of 0 to 10, with 0 being no pain and 10 being the worst pain imaginable, what is your current pain level?' },
  { field: 'treatments', question: 'What treatments have you tried so far? For example: physical therapy, injections, medications, or surgery?' },
  { field: 'meds', question: 'Please list your current medications.' },
  { field: 'allergies', question: 'Do you have any allergies to medications or other substances?' },
  { field: 'conditions', question: 'Do you have any medical conditions such as diabetes, high blood pressure, heart disease, cancer, or others?' },
  { field: 'surgeries', question: 'Have you had any surgeries? If so, please describe them.' },
  { field: 'hosps', question: 'Have you had any hospitalizations? If so, please tell me about them.' },
  { field: 'fam_hx', question: 'Is there any family history of cancer, diabetes, heart disease, or stroke?' },
  { field: 'marital', question: 'What is your marital status? Married, single, divorced, or separated?' },
  { field: 'employment', question: 'What is your current employment status or occupation?' },
  { field: 'smoking', question: 'Do you smoke?' },
  { field: 'alcohol', question: 'Do you drink alcohol?' },
  { field: 'disability', question: 'Are you currently applying for disability benefits?' },
  { field: 'ros_const', question: 'Have you noticed any recent weight changes, unusual weakness, fatigue, or fever?' },
  { field: 'ros_cardio', question: 'Have you had any chest pain, shortness of breath, heart palpitations, or high blood pressure?' },
  { field: 'ros_neuro', question: 'Have you experienced any numbness, tingling, weakness, blackouts, seizures, or memory problems?' },
  { field: 'ros_msk', question: 'Besides your main complaint, do you have any other joint pain, stiffness, or limited range of motion?' },
  { field: 'ros_psych', question: 'Have you been experiencing any anxiety, depression, mood changes, or significant stress?' },
  { field: 'ros_other', question: 'Are there any other symptoms I have not asked about that you would like to mention?' },
  { field: 'pregnant', question: 'Are you currently pregnant or planning to become pregnant?' },
  { field: 'consent', question: 'Finally, do you authorize Global Neuro and Spine Institute to use your information to process your claims and treatment? Please say yes or no.' },
];

const FOLLOWUP_QUESTIONS = [
  { field: 'full_name', question: 'What is your full name?' },
  { field: 'chief_complaint', question: 'What is your main complaint today?' },
  { field: 'pain_loc', question: 'Where is your pain located?' },
  { field: 'pain_worse', question: 'What makes your pain worse?' },
  { field: 'pain_better', question: 'What makes your pain better?' },
  { field: 'pain_desc', question: 'How would you describe your pain, sharp, burning, shooting, achy, or pressure?' },
  { field: 'pain_sev', question: 'On a scale of 0 to 10, what is your current pain level?' },
  { field: 'had_proc', question: 'Did you have a procedure during your last visit?' },
  { field: 'proc_relief', question: 'How much pain relief did that procedure provide? Less than 25 percent, 25 to 50 percent, 50 to 75 percent, or more than 75 percent?' },
  { field: 'new_meds', question: 'Are you taking any new medications since your last visit?' },
  { field: 'new_cond', question: 'Have you had any new illnesses, injuries, surgeries, or hospitalizations since your last visit?' },
  { field: 'fam_chg', question: 'Any changes in your family history since your last visit?' },
  { field: 'soc_chg', question: 'Any changes in your social history, such as marital status, employment, or substance use?' },
  { field: 'disability', question: 'Are you currently applying for disability benefits?' },
  { field: 'ros', question: 'Are you experiencing any new symptoms today such as chest pain, shortness of breath, numbness, or tingling?' },
  { field: 'ros_other', question: 'Anything else you would like to mention before your appointment?' },
];

// In-memory session store — keyed by Twilio CallSid
// Works well for demo; upgrade to Vercel KV for production
const sessions = new Map();

export async function POST(request) {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'https://voiceintake.vercel.app';

  let formData;
  try {
    formData = await request.formData();
  } catch (e) {
    console.error('FormData parse error:', e);
    return errorResponse(baseUrl);
  }

  const speechResult = (formData.get('SpeechResult') || '').trim();
  const callSid = formData.get('CallSid') || '';

  const url = new URL(request.url);
  const flowType = url.searchParams.get('flow') || 'new';

  console.log(`[${callSid}] Speech: "${speechResult}"`);

  // Get or initialize session
  let session = sessions.get(callSid);
  if (!session) {
    session = {
      flowType,
      callSid,
      questionIndex: 0,
      allResponses: {},
      chatHistory: [],
    };
    sessions.set(callSid, session);
  }

  const questions = session.flowType === 'followup' ? FOLLOWUP_QUESTIONS : NEW_PATIENT_QUESTIONS;
  const currentQ = questions[session.questionIndex];

  // No speech — repeat current question
  if (!speechResult) {
    return new NextResponse(
      buildGatherTwiml("I am sorry, I did not hear that. " + currentQ.question, callSid, session.flowType, baseUrl),
      { headers: { 'Content-Type': 'text/xml' } }
    );
  }

  // Process with Claude
  let claudeResponse;
  try {
    claudeResponse = await processWithClaude(speechResult, session, questions);
  } catch (err) {
    console.error(`[${callSid}] Claude error:`, err);
    return new NextResponse(
      buildGatherTwiml("I am sorry, I had a technical hiccup. Could you repeat that?", callSid, session.flowType, baseUrl),
      { headers: { 'Content-Type': 'text/xml' } }
    );
  }

  const { action, updates, reply, skipTo } = claudeResponse;

  // Update session in place
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

  sessions.set(callSid, session);

  // All questions answered — wrap up
  if (session.questionIndex >= questions.length) {
    sessions.delete(callSid);
    console.log(`[${callSid}] Intake complete:`, session.allResponses);

    const doneTwiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural" rate="90%">${escapeXml(reply)}</Say>
  <Pause length="1"/>
  <Say voice="Polly.Joanna-Neural" rate="90%">Your intake is now complete. Thank you so much for your time. Our clinical team will review your information before your appointment. Have a great day and goodbye!</Say>
</Response>`;
    return new NextResponse(doneTwiml, { headers: { 'Content-Type': 'text/xml' } });
  }

  return new NextResponse(
    buildGatherTwiml(reply, callSid, session.flowType, baseUrl),
    { headers: { 'Content-Type': 'text/xml' } }
  );
}

async function processWithClaude(speech, session, questions) {
  const currentQ = questions[session.questionIndex];
  const nextQ = questions[session.questionIndex + 1];
  const patientName = session.allResponses['full_name'] || '';
  const firstName = patientName.split(' ')[0] || '';

  const systemPrompt = `You are Sarah, a warm and friendly medical intake assistant for Global Neuro and Spine Institute, a pain management practice in Florida. You are on a phone call — speak naturally like a caring nurse, not a robot.

CRITICAL RULES:
1. Keep ALL replies to 1-2 SHORT sentences. They are spoken aloud on a phone call.
2. When advancing, include BOTH a brief acknowledgment AND the next question in one reply.
3. Never repeat questions already answered.
4. If patient corrects something, use action="stay", fix it, do not advance.
5. If patient gives multiple answers at once, capture all with skipTo to jump ahead.
6. ${firstName ? `Address the patient as ${firstName} occasionally.` : 'Use a warm friendly tone.'}
7. Understand patient phrasings: "water pill"=diuretic, "sugar"=diabetes, "bad back"=lumbar pain, "blood thinner"=anticoagulant, "nerve pain"=neuropathic pain.
8. Accept casual yes/no: "yeah", "nope", "uh huh", "nah" are all valid.
9. Sound natural — avoid "I understand", "Great!", "Certainly!" — those sound robotic.
10. Speak as if talking to an elderly patient — clear, warm, patient, no jargon.

SPECIAL FIELD HANDLING:
- If current field is "name_spelling": Patient will spell out their name letter by letter or say it. Capture the spelling exactly. Then in your reply, read it back formatted like: "Let me make sure I have that right. Your name is [full name], first name spelled [F-I-R-S-T], last name spelled [L-A-S-T]. Is that correct?"
- If current field is "name_confirm": Patient will say yes/correct or give a correction. If correct, advance. If they correct anything, update full_name and name_spelling, stay and read back the corrected version for re-confirmation. Only advance once they confirm it is correct.

CURRENT STATE:
- Visit type: ${session.flowType === 'followup' ? 'Follow-up visit' : 'New patient visit'}
- Current field: ${currentQ?.field}
- Current question: "${currentQ?.question}"
- Next question: "${nextQ?.question || 'This is the last question. Thank the patient warmly and let them know they are all done.'}"
- Fields collected so far: ${Object.keys(session.allResponses).join(', ') || 'none yet'}
- Full name collected: ${session.allResponses['full_name'] || 'not yet'}
- Name spelling collected: ${session.allResponses['name_spelling'] || 'not yet'}

Respond ONLY with valid JSON — no markdown, no backticks, nothing else:
{"action":"advance","updates":{"field_name":"value"},"reply":"your spoken reply here","skipTo":null}`;

  const response = await anthropic.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 250,
    system: systemPrompt,
    messages: [
      ...session.chatHistory.slice(-8).map(h => ({ role: h.role, content: h.content })),
      { role: 'user', content: speech },
    ],
  });

  const text = response.content[0].text.trim();

  try {
    return JSON.parse(text);
  } catch (e) {
    console.error('Claude JSON parse error:', text);
    return { action: 'stay', updates: {}, reply: "Could you say that again please?", skipTo: null };
  }
}

function buildGatherTwiml(replyText, callSid, flowType, baseUrl) {
  const actionUrl = `${baseUrl}/api/call/respond?flow=${flowType}`;
  return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural" rate="90%">${escapeXml(replyText)}</Say>
  <Gather
    input="speech"
    action="${actionUrl}"
    method="POST"
    speechTimeout="3"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="12"
  >
  </Gather>
  <Say voice="Polly.Joanna-Neural" rate="90%">I did not catch that. ${escapeXml(replyText)}</Say>
  <Gather
    input="speech"
    action="${actionUrl}"
    method="POST"
    speechTimeout="3"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="12"
  >
  </Gather>
  <Say voice="Polly.Joanna-Neural">I am having trouble hearing you. Please try calling back. Goodbye.</Say>
  <Hangup/>
</Response>`;
}

function errorResponse(baseUrl) {
  return new NextResponse(`<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural">I am sorry, something went wrong. Please try calling back in a moment. Goodbye.</Say>
  <Hangup/>
</Response>`, { headers: { 'Content-Type': 'text/xml' } });
}

function escapeXml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
