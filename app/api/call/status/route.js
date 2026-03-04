import { NextResponse } from 'next/server';

export async function POST(request) {
  const formData = await request.formData();
  const callSid = formData.get('CallSid');
  const callStatus = formData.get('CallStatus');
  const callDuration = formData.get('CallDuration');
  const from = formData.get('From');

  console.log(`Call completed | SID: ${callSid} | Status: ${callStatus} | Duration: ${callDuration}s | From: ${from}`);

  return new NextResponse('OK', { status: 200 });
}
