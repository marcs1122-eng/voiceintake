// /app/api/session/route.js
// GET  ?phone=17723251556  → returns saved partial session for that phone number
// GET  ?id=call_abc123     → returns intake record for that call ID
// DELETE ?phone=...        → clears session after successful completion

import { Redis } from '@upstash/redis';

const redis = new Redis({
  url: process.env.KV_REST_API_URL,
  token: process.env.KV_REST_API_TOKEN,
});

export async function GET(req) {
  try {
    const { searchParams } = new URL(req.url);
    const phone = searchParams.get('phone');
    const id = searchParams.get('id');
    if (!phone && !id) {
      return new Response(JSON.stringify({ error: 'Provide phone or id param' }), { status: 400 });
    }
    let data = null;
    if (phone) {
      data = await redis.get(`session:${phone.replace(/\D/g, '')}`);
    } else if (id) {
      data = await redis.get(`intake:${id}`);
    }
    if (!data) return new Response(JSON.stringify({ found: false }), { status: 200 });
    const parsed = typeof data === 'string' ? JSON.parse(data) : data;
    return new Response(JSON.stringify({ found: true, session: parsed }), { status: 200 });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
}

export async function DELETE(req) {
  try {
    const { searchParams } = new URL(req.url);
    const phone = searchParams.get('phone');
    if (!phone) return new Response(JSON.stringify({ error: 'phone required' }), { status: 400 });
    await redis.del(`session:${phone.replace(/\D/g, '')}`);
    return new Response(JSON.stringify({ deleted: true }), { status: 200 });
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), { status: 500 });
  }
}
