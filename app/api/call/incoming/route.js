import { NextResponse } from 'next/server';

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://voiceintake.vercel.app';

export async function POST(request) {
  const { searchParams } = new URL(request.url);
  const flowType = searchParams.get('flow') || 'new';
  const formData = await request.formData();
  const callSid = formData.get('CallSid') || '';

  console.log(`Incoming call: ${callSid}, flow: ${flowType}`);

  const greeting = flowType === 'followup'
    ? "Hello! Welcome to Global Neuro and Spine Institute. I'm Sarah, your virtual intake assistant. I'll collect some brief information for your follow-up today \u2014 just a few minutes. Let's start \u2014 what's your full name?"
    : "Hello! Welcome to Global Neuro and Spine Institute. I'm Sarah, your virtual intake assistant. I'll gather your information before your appointment \u2014 takes about 5 to 10 minutes. Let's begin \u2014 what's your full name?";

  const audioUrl = `${BASE_URL}/api/audio?text=${encodeURIComponent(greeting)}`;
  const actionUrl = `${BASE_URL}/api/call/respond?flow=${flowType}`;

  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="${actionUrl}" method="POST" speechTimeout="1" speechModel="phone_call" enhanced="true" language="en-US" timeout="12">
    <Play>${audioUrl}</Play>
  </Gather>
  <Gather input="speech" action="${actionUrl}" method="POST" speechTimeout="1" speechModel="phone_call" enhanced="true" language="en-US" timeout="12">
    <Play>${BASE_URL}/api/audio?text=${encodeURIComponent("I didn't catch that. What's your full name?")}</Play>
  </Gather>
  <Play>${BASE_URL}/api/audio?text=${encodeURIComponent("I'm having trouble hearing you. Please try calling back. Goodbye.")}</Play>
  <Hangup/>
</Response>`;

  return new NextResponse(twiml, {
    headers: { 'Content-Type': 'text/xml' },
  });
}
