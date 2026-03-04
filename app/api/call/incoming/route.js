import { NextResponse } from 'next/server';

const BASE_URL = 'https://voiceintake.vercel.app';

export async function POST(request) {
  const url = new URL(request.url);
  const flowType = url.searchParams.get('flow') || 'new';

  const formData = await request.formData();
  const callSid = formData.get('CallSid') || '';

  console.log(`Incoming call: ${callSid}, flow: ${flowType}`);

  const greeting = flowType === 'followup'
    ? "Hello! Welcome to Global Neuro and Spine Institute. I'm your virtual intake assistant and I'll be collecting some brief information for your follow-up visit today. This will only take a few minutes. Let's start — what is your full name?"
    : "Hello! Welcome to Global Neuro and Spine Institute. I'm your virtual intake assistant and I'll be collecting your information before your appointment today. This takes about 5 to 10 minutes. Let's begin — what is your full name?";

  const audioUrl = `${BASE_URL}/api/audio?text=${encodeURIComponent(greeting)}`;
  const actionUrl = `${BASE_URL}/api/call/respond?flow=${flowType}`;

  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather
    input="speech"
    action="${actionUrl}"
    method="POST"
    speechTimeout="2"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="12"
  >
    <Play>${audioUrl}</Play>
  </Gather>
  <Gather
    input="speech"
    action="${actionUrl}"
    method="POST"
    speechTimeout="2"
    speechModel="phone_call"
    enhanced="true"
    language="en-US"
    timeout="12"
  >
    <Play>${BASE_URL}/api/audio?text=${encodeURIComponent("I didn't catch that. What is your full name?")}</Play>
  </Gather>
  <Play>${BASE_URL}/api/audio?text=${encodeURIComponent("I'm having trouble hearing you. Please try calling back. Goodbye.")}</Play>
  <Hangup/>
</Response>`;

  return new NextResponse(twiml, {
    headers: { 'Content-Type': 'text/xml' },
  });
}
