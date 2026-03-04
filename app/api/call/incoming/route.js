import { NextResponse } from 'next/server';

export async function POST(request) {
  const formData = await request.formData();
  const callSid = formData.get('CallSid');
  const flowType = new URL(request.url).searchParams.get('flow') || 'new';

  console.log(`Incoming call: ${callSid}, flow: ${flowType}`);

  const greeting = flowType === 'followup'
    ? "Hello! Welcome to Global Neuro and Spine Institute. I'm your virtual intake assistant and I'll be collecting some brief information for your follow-up visit today. This will only take a few minutes. Let's start — what is your full name?"
    : "Hello! Welcome to Global Neuro and Spine Institute. I'm your virtual intake assistant and I'll be collecting your information before your appointment today. This takes about 5 to 10 minutes. Please speak clearly and I'll guide you through each question. Let's begin — what is your full name?";

  const initialState = {
    flowType,
    callSid,
    currentField: 'full_name',
    allResponses: {},
    chatHistory: [],
    questionIndex: 0,
  };

  const stateParam = encodeURIComponent(JSON.stringify(initialState));

  const baseUrl = process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : process.env.NEXT_PUBLIC_BASE_URL || 'https://voiceintake.vercel.app';

  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna" rate="95%">${escapeXml(greeting)}</Say>
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
    <Say voice="Polly.Joanna" rate="95%">I'm listening.</Say>
  </Gather>
  <Say voice="Polly.Joanna">I didn't catch that. Let me try again.</Say>
  <Redirect method="POST">${baseUrl}/api/call/incoming?flow=${flowType}</Redirect>
</Response>`;

  return new NextResponse(twiml, {
    headers: { 'Content-Type': 'text/xml' },
  });
}

function escapeXml(str) {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}
