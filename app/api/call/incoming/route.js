import { NextResponse } from 'next/server';

export async function POST(request) {
  const url = new URL(request.url);
  const flowType = url.searchParams.get('flow') || 'new';

  const formData = await request.formData();
  const callSid = formData.get('CallSid') || '';

  // Hardcoded production URL — most reliable approach
  const baseUrl = 'https://voiceintake.vercel.app';

  console.log(`Incoming call: ${callSid}, flow: ${flowType}`);

  const greeting = flowType === 'followup'
    ? "Hello! Welcome to Global Neuro and Spine Institute. I am your virtual intake assistant and I will be collecting some brief information for your follow-up visit today. This will only take a few minutes. Let us start. What is your full name?"
    : "Hello! Welcome to Global Neuro and Spine Institute. I am your virtual intake assistant and I will be collecting your information before your appointment today. This takes about 5 to 10 minutes. Please speak clearly after each question. Let us begin. What is your full name?";

  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna" rate="90%">${escapeXml(greeting)}</Say>
  <Gather
    input="speech"
    action="${baseUrl}/api/call/respond?flow=${flowType}"
    method="POST"
    speechTimeout="3"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="12"
  >
  </Gather>
  <Say voice="Polly.Joanna" rate="90%">I did not catch that. What is your full name?</Say>
  <Gather
    input="speech"
    action="${baseUrl}/api/call/respond?flow=${flowType}"
    method="POST"
    speechTimeout="3"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="12"
  >
  </Gather>
  <Say voice="Polly.Joanna">I am having trouble hearing you. Please try calling back. Goodbye.</Say>
  <Hangup/>
</Response>`;

  return new NextResponse(twiml, {
    headers: { 'Content-Type': 'text/xml' },
  });
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
