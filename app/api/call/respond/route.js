import { NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

const NEW_PATIENT_QUESTIONS = [
  { field: 'full_name', question: 'What is your full name?' },
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
  { field: 'ros_other', question: "Are there any other symptoms I haven't asked about that you'd like to mention?" },
  { field: 'pregnant', question: 'Are you currently pregnant or planning to become pregnant?' },
  { field: 'consent', question: 'Finally, do you authorize Global Neuro and Spine Institute to use your information to process your claims and treatment? Please say yes or no.' },
];

const FOLLOWUP_QUESTIONS = [
  { field: 'full_name', question: 'What is your full name?' },
  { field: 'chief_complaint', question: 'What is your main complaint today?' },
  { field: 'pain_loc', question: 'Where is your pain located?' },
  { field: 'pain_worse', question: 'What makes your pain worse?' },
  { field: 'pain_better', question: 'What makes your pain better?' },
  { field: 'pain_desc', question: 'How would you describe your pain — sharp, burning, shooting, achy, or pressure?' },
  { field: 'pain_sev', question: 'On a scale of 0 to 10, what is your current pain level?' },
  { field: 'had_proc', question: 'Did you have a procedure during your last visit?' },
  { field: 'proc_relief', question: 'How much pain relief did that procedure provide — less than 25 percent, 25 to 50 percent, 50 to 75 percent, or more than 75 percent?' },
  { field: 'new_meds', question: 'Are you taking any new medications since your last visit?' },
  { field: 'new_cond', question: 'Have you had any new illnesses, injuries, surgeries, or hospitalizations since your last visit?' },
  { field: 'fam_chg', question: 'Any changes in your family history since your last visit?' },
  { field: 'soc_chg', question: 'Any changes in your social history — such as marital status, employment, or substance use?' },
  { field: 'disability', question: 'Are you currently applying for disability benefits?' },
  { field: 'ros', question: 'Are you experiencing any new symptoms today? For example: chest pain, shortness of breath, numbness, tingling, or anything else unusual?' },
  { field: 'ros_other', question: "Anything else you'd like to mention before your appointment?" },
];

export async function POST(request) {
  const formData = await request.formData();
  const speechResult = formData.get('SpeechResult') || '';
  const callSid = formData.get('CallSid');

  const url = new URL(request.url);
  const baseUrl = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : process.env.NEXT_PUBLIC_BASE_URL || 'https://voiceintake.vercel.app';

  let state;
  try {
    state = JSON.parse(decodeURIComponent(url.searchParams.get('state') || '{}'));
  } catch (e) {
    console.error('State parse error:', e);
    return errorResponse(baseUrl);
  }

  const { flowType = 'new', currentField, allResponses = {}, chatHistory = [], questionIndex = 0 } = state;
  const questions = flowType === 'followup' ? FOLLOWUP_QUESTIONS : NEW_PATIENT_QUESTIONS;

  console.log(`Call ${callSid} | Field: ${currentField} | Speech: "${speechResult}"`);

  if (!speechResult || speechResult.trim() === '') {
    const retryTwiml = buildGatherTwiml(
      "I'm sorry, I didn't hear that. Could you please repeat your answer?",
      buildStateParam(state),
      baseUrl
    );
    return new NextResponse(retryTwiml, { headers: { 'Content-Type': 'text/xml' } });
  }

  let claudeResponse;
  try {
    claudeResponse = await processWithClaude({
      speech: speechResult,
      currentField,
      allResponses,
      chatHistory,
      questionIndex,
      questions,
      flowType,
    });
  } catch (err) {
    console.error('Claude error:', err);
    return errorResponse(baseUrl);
  }

  const { action, updates, reply, skipTo } = claudeResponse;

  const newResponses = { ...allResponses, ...updates };
  const newHistory = [
    ...chatHistory,
    { role: 'user', content: speechResult },
    { role: 'assistant', content: reply },
  ].slice(-20);

  let nextIndex = questionIndex;
  let nextField = currentField;

  if (action === 'advance') {
    if (skipTo) {
      const skipIndex = questions.findIndex(q => q.field === skipTo);
      nextIndex = skipIndex !== -1 ? skipIndex : questionIndex + 1;
      nextField = questions[nextIndex]?.field || 'done';
    } else {
      nextIndex = questionIndex + 1;
      nextField = questions[nextIndex]?.field || 'done';
    }
  }

  if (nextField === 'done' || nextIndex >= questions.length) {
    const closingTwiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna" rate="95%">${escapeXml(reply)}</Say>
  <Say voice="Polly.Joanna" rate="95%">Your intake is now complete. Thank you for taking the time to complete this. The clinical team will review your information before your appointment. You may hang up now. Goodbye!</Say>
</Response>`;
    return new NextResponse(closingTwiml, { headers: { 'Content-Type': 'text/xml' } });
  }

  const newState = {
    flowType,
    callSid,
    currentField: nextField,
    allResponses: newResponses,
    chatHistory: newHistory,
    questionIndex: nextIndex,
  };

  const twiml = buildGatherTwiml(reply, buildStateParam(newState), baseUrl);
  return new NextResponse(twiml, { headers: { 'Content-Type': 'text/xml' } });
}

async function processWithClaude({ speech, currentField, allResponses, chatHistory, questionIndex, questions, flowType }) {
  const currentQ = questions[questionIndex];
  const nextQ = questions[questionIndex + 1];
  const answeredFields = Object.keys(allResponses);

  const systemPrompt = `You are a warm, friendly medical intake assistant for Global Neuro and Spine Institute, a pain management practice in Florida. You are conducting a patient intake over the phone — like a kind, efficient nurse.

CRITICAL RULES:
1. Keep ALL replies to 1-2 short sentences maximum. These are spoken aloud on a phone call.
2. When advancing, include BOTH your acknowledgment AND the next question in your reply.
3. Never repeat questions already answered.
4. If the patient corrects something, use action="stay" and fix it without advancing.
5. If the patient gives multiple answers at once, capture all of them and skip ahead with skipTo.
6. Use the patient's first name once you know it.
7. Be warm but efficient — elderly patients appreciate clarity.
8. Understand common patient phrasings: "water pill" = diuretic, "sugar" = diabetes, "bad back" = lumbar pain, "BP" = blood pressure.

CURRENT INTAKE STATE:
- Visit type: ${flowType === 'followup' ? 'Follow-up visit' : 'New patient'}
- Current question field: ${currentField}
- Current question: "${currentQ?.question}"
- Next question: "${nextQ?.question || 'This is the last question'}"
- Already collected: ${JSON.stringify(answeredFields)}

Respond ONLY with a valid JSON object — no markdown, no backticks, no extra text:
{
  "action": "advance" or "stay",
  "updates": { "field_name": "captured value" },
  "reply": "Your spoken response including next question if advancing",
  "skipTo": "field_name" or null
}`;

  const messages = [
    ...chatHistory.slice(-10).map(h => ({ role: h.role, content: h.content })),
    { role: 'user', content: speech },
  ];

  const response = await anthropic.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 300,
    system: systemPrompt,
    messages,
  });

  const text = response.content[0].text.trim();

  try {
    return JSON.parse(text);
  } catch (e) {
    console.error('Claude JSON parse error:', text);
    return {
      action: 'stay',
      updates: {},
      reply: "I'm sorry, could you repeat that?",
      skipTo: null,
    };
  }
}

function buildGatherTwiml(replyText, stateParam, baseUrl) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna" rate="95%">${escapeXml(replyText)}</Say>
  <Gather
    input="speech"
    action="${baseUrl}/api/call/respond?state=${stateParam}"
    method="POST"
    speechTimeout="2"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="10"
  >
  </Gather>
  <Say voice="Polly.Joanna">I didn't catch that. ${escapeXml(replyText)}</Say>
  <Gather
    input="speech"
    action="${baseUrl}/api/call/respond?state=${stateParam}"
    method="POST"
    speechTimeout="2"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="10"
  >
  </Gather>
  <Say voice="Polly.Joanna">I'm having trouble hearing you. Please call back and we'll try again. Goodbye.</Say>
  <Hangup/>
</Response>`;
}

function buildStateParam(state) {
  const trimmed = {
    ...state,
    chatHistory: state.chatHistory?.slice(-6) || [],
  };
  return encodeURIComponent(JSON.stringify(trimmed));
}

function errorResponse(baseUrl) {
  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">I'm sorry, I'm having a technical issue. Please call back in a moment. Goodbye.</Say>
  <Hangup/>
</Response>`;
  return new NextResponse(twiml, { headers: { 'Content-Type': 'text/xml' } });
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
