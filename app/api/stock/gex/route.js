// FlashAlpha gamma exposure proxy.
// Calls https://lab.flashalpha.com/v1/exposure/gex/<TICKER> and returns
// whatever the upstream provides, with light error normalization.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const FLASHALPHA_API_KEY = "DT7Y8Eh48BtXDAbVqwghmGBk7KtGkqkCrmAQ2Ew5";
const FLASHALPHA_BASE = "https://lab.flashalpha.com/v1";

async function handle(rawTicker) {
  var ticker = (rawTicker || "").toString().trim().toUpperCase();
  if (!ticker) {
    return new Response(JSON.stringify({ error: "Missing ticker" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  var url = FLASHALPHA_BASE + "/exposure/gex/" + encodeURIComponent(ticker);

  try {
    var res = await fetch(url, {
      headers: {
        "X-Api-Key": FLASHALPHA_API_KEY,
        Accept: "application/json",
      },
      cache: "no-store",
    });

    var text = await res.text();
    var body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch (e) {
      body = { raw: text };
    }

    if (!res.ok) {
      return new Response(
        JSON.stringify({
          error:
            (body && (body.error || body.message)) ||
            "FlashAlpha request failed (" + res.status + ")",
          status: res.status,
        }),
        { status: res.status, headers: { "Content-Type": "application/json" } }
      );
    }

    return new Response(JSON.stringify({ ticker: ticker, gex: body }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(
      JSON.stringify({ error: e.message || "Network error" }),
      { status: 502, headers: { "Content-Type": "application/json" } }
    );
  }
}

export async function POST(request) {
  var body;
  try {
    body = await request.json();
  } catch (e) {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }
  return handle(body && body.ticker);
}

export async function GET(request) {
  var url = new URL(request.url);
  return handle(url.searchParams.get("ticker"));
}
