import { kv } from '@vercel/kv';

export const runtime = 'nodejs';

function checkAuth(request) {
  const auth = request.headers.get('Authorization') || '';
  const token = auth.replace('Bearer ', '').trim();
  return token === process.env.ADMIN_PASSWORD;
}

export async function GET(request) {
  if (!checkAuth(request)) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const callSids = await kv.lrange('intakes:index', 0, 99);
    if (!callSids || callSids.length === 0) {
      return Response.json({ intakes: [] });
    }
    const intakes = await Promise.all(callSids.map(sid => kv.get('intake:' + sid)));
    return Response.json({ intakes: intakes.filter(Boolean) });
  } catch (error) {
    console.error('[admin/intakes] Error:', error);
    return Response.json({ error: error.message }, { status: 500 });
  }
}
