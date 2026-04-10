// Stock intrinsic value calculator.
// Pulls live fundamentals from Yahoo Finance (no API key required) and
// runs several valuation models, then optionally asks Claude for a
// qualitative thesis when ANTHROPIC_API_KEY is configured.

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const YAHOO_MODULES = [
  "price",
  "summaryDetail",
  "summaryProfile",
  "defaultKeyStatistics",
  "financialData",
  "incomeStatementHistory",
  "balanceSheetHistory",
  "cashflowStatementHistory",
  "earnings",
  "earningsTrend",
].join(",");

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

// Pull a raw number out of Yahoo's { raw, fmt } shape, tolerating missing data.
function num(obj, ...path) {
  var cur = obj;
  for (var i = 0; i < path.length; i++) {
    if (cur == null) return null;
    cur = cur[path[i]];
  }
  if (cur == null) return null;
  if (typeof cur === "number") return isFinite(cur) ? cur : null;
  if (typeof cur === "object" && "raw" in cur) {
    var r = cur.raw;
    return typeof r === "number" && isFinite(r) ? r : null;
  }
  return null;
}

function firstStatement(list) {
  if (!list || !Array.isArray(list) || list.length === 0) return null;
  return list[0];
}

async function fetchYahoo(ticker) {
  var url =
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/" +
    encodeURIComponent(ticker) +
    "?modules=" +
    YAHOO_MODULES;

  var res = await fetch(url, {
    headers: {
      "User-Agent": UA,
      Accept: "application/json,text/plain,*/*",
      "Accept-Language": "en-US,en;q=0.9",
    },
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error("Yahoo Finance request failed: " + res.status);
  }

  var data = await res.json();
  if (data && data.quoteSummary && data.quoteSummary.error) {
    throw new Error(data.quoteSummary.error.description || "Ticker not found");
  }
  var result = data && data.quoteSummary && data.quoteSummary.result;
  if (!result || !result[0]) {
    throw new Error("No data returned for ticker " + ticker);
  }
  return result[0];
}

function extractFundamentals(q) {
  var price = q.price || {};
  var summary = q.summaryDetail || {};
  var stats = q.defaultKeyStatistics || {};
  var fin = q.financialData || {};
  var profile = q.summaryProfile || {};

  var income = firstStatement(
    q.incomeStatementHistory && q.incomeStatementHistory.incomeStatementHistory
  );
  var balance = firstStatement(
    q.balanceSheetHistory && q.balanceSheetHistory.balanceSheetStatements
  );
  var cashflow = firstStatement(
    q.cashflowStatementHistory && q.cashflowStatementHistory.cashflowStatements
  );

  var incomeList =
    (q.incomeStatementHistory &&
      q.incomeStatementHistory.incomeStatementHistory) ||
    [];
  var cashflowList =
    (q.cashflowStatementHistory &&
      q.cashflowStatementHistory.cashflowStatements) ||
    [];

  // Historical revenue / earnings series, oldest first.
  var revSeries = incomeList
    .map(function (r) {
      return num(r, "totalRevenue");
    })
    .filter(function (v) {
      return v != null;
    })
    .reverse();
  var niSeries = incomeList
    .map(function (r) {
      return num(r, "netIncome");
    })
    .filter(function (v) {
      return v != null;
    })
    .reverse();

  // Free cash flow = operating cash flow - capital expenditures (capex is negative)
  var fcfSeries = cashflowList
    .map(function (r) {
      var op = num(r, "totalCashFromOperatingActivities");
      var capex = num(r, "capitalExpenditures");
      if (op == null) return null;
      if (capex == null) return op;
      return op + capex; // capex is stored as negative
    })
    .filter(function (v) {
      return v != null;
    })
    .reverse();

  // 5-yr analyst EPS growth estimate (decimal, e.g. 0.12)
  var analystGrowth5y = null;
  var trend =
    q.earningsTrend && q.earningsTrend.trend ? q.earningsTrend.trend : [];
  for (var i = 0; i < trend.length; i++) {
    if (trend[i].period === "+5y") {
      analystGrowth5y = num(trend[i], "growth");
      break;
    }
  }

  return {
    ticker: price.symbol || null,
    name: price.longName || price.shortName || null,
    currency: price.currency || "USD",
    exchange: price.exchangeName || null,
    sector: profile.sector || null,
    industry: profile.industry || null,

    currentPrice:
      num(price, "regularMarketPrice") || num(fin, "currentPrice"),
    marketCap: num(price, "marketCap"),
    sharesOutstanding:
      num(stats, "sharesOutstanding") || num(stats, "impliedSharesOutstanding"),

    trailingEps: num(stats, "trailingEps"),
    forwardEps: num(stats, "forwardEps"),
    bookValuePerShare: num(stats, "bookValue"),
    beta: num(stats, "beta"),

    trailingPE: num(summary, "trailingPE"),
    forwardPE: num(summary, "forwardPE"),
    priceToBook: num(stats, "priceToBook"),
    dividendRate: num(summary, "dividendRate"),
    dividendYield: num(summary, "dividendYield"),
    payoutRatio: num(summary, "payoutRatio"),

    totalCash: num(fin, "totalCash"),
    totalDebt: num(fin, "totalDebt"),
    freeCashflow: num(fin, "freeCashflow"),
    operatingCashflow: num(fin, "operatingCashflow"),
    returnOnEquity: num(fin, "returnOnEquity"),
    profitMargins: num(fin, "profitMargins"),
    revenueGrowth: num(fin, "revenueGrowth"),
    earningsGrowth: num(fin, "earningsGrowth"),

    totalRevenue: num(income, "totalRevenue"),
    netIncome: num(income, "netIncome"),
    totalStockholderEquity: num(balance, "totalStockholderEquity"),
    operatingCashflowLatest: num(cashflow, "totalCashFromOperatingActivities"),
    capexLatest: num(cashflow, "capitalExpenditures"),

    analystGrowth5y: analystGrowth5y,
    revSeries: revSeries,
    niSeries: niSeries,
    fcfSeries: fcfSeries,
  };
}

// Compound annual growth rate of a series (oldest -> newest).
function cagr(series) {
  if (!series || series.length < 2) return null;
  var first = series[0];
  var last = series[series.length - 1];
  if (first == null || last == null) return null;
  if (first <= 0 || last <= 0) return null;
  var years = series.length - 1;
  return Math.pow(last / first, 1 / years) - 1;
}

function clamp(v, lo, hi) {
  if (v == null || !isFinite(v)) return null;
  return Math.max(lo, Math.min(hi, v));
}

// ---- Valuation models ---------------------------------------------------

// Two-stage discounted cash flow on free cash flow.
function dcfModel(f) {
  var fcf = f.freeCashflow;
  if (fcf == null && f.fcfSeries.length > 0) {
    fcf = f.fcfSeries[f.fcfSeries.length - 1];
  }
  if (fcf == null || fcf <= 0) {
    return { ok: false, reason: "No positive free cash flow available" };
  }
  if (!f.sharesOutstanding || f.sharesOutstanding <= 0) {
    return { ok: false, reason: "Shares outstanding unknown" };
  }

  // Growth inputs: blend analyst + historical, clamp to sane range.
  var histFcfGrowth = cagr(f.fcfSeries);
  var histRevGrowth = cagr(f.revSeries);
  var candidates = [f.analystGrowth5y, histFcfGrowth, histRevGrowth, f.earningsGrowth];
  var valid = candidates.filter(function (v) {
    return v != null && isFinite(v);
  });
  var g1;
  if (valid.length === 0) {
    g1 = 0.05;
  } else {
    var sum = 0;
    for (var i = 0; i < valid.length; i++) sum += valid[i];
    g1 = sum / valid.length;
  }
  g1 = clamp(g1, -0.05, 0.2); // cap stage-1 growth at 20%, floor at -5%
  var g2 = 0.025; // long-run terminal growth
  var discount = 0.09; // WACC-ish default
  if (f.beta && f.beta > 0) {
    // CAPM-lite: risk-free 4% + beta * 5% equity risk premium, floor 7%, cap 12%
    discount = clamp(0.04 + f.beta * 0.05, 0.07, 0.12);
  }

  var years = 10;
  var projected = [];
  var cash = fcf;
  var pvSum = 0;
  for (var y = 1; y <= years; y++) {
    cash = cash * (1 + g1);
    var pv = cash / Math.pow(1 + discount, y);
    projected.push({ year: y, fcf: cash, pv: pv });
    pvSum += pv;
  }
  // Terminal value via Gordon growth model
  var terminalFcf = cash * (1 + g2);
  var terminalValue = terminalFcf / (discount - g2);
  var terminalPv = terminalValue / Math.pow(1 + discount, years);

  var enterpriseValue = pvSum + terminalPv;
  var equityValue =
    enterpriseValue + (f.totalCash || 0) - (f.totalDebt || 0);
  var perShare = equityValue / f.sharesOutstanding;

  return {
    ok: true,
    name: "Discounted Cash Flow (10yr, 2-stage)",
    intrinsicPerShare: perShare,
    assumptions: {
      startingFcf: fcf,
      growthStage1: g1,
      growthTerminal: g2,
      discountRate: discount,
      years: years,
      terminalValue: terminalValue,
    },
    detail: {
      pvOfProjectedFcf: pvSum,
      pvOfTerminal: terminalPv,
      enterpriseValue: enterpriseValue,
      equityValue: equityValue,
    },
  };
}

// Benjamin Graham's revised intrinsic value formula.
// V = EPS * (8.5 + 2g) * 4.4 / Y  where Y is the current AAA corporate bond yield.
function grahamFormula(f) {
  var eps = f.trailingEps;
  if (eps == null || eps <= 0) {
    return { ok: false, reason: "No positive trailing EPS" };
  }
  var growthPct;
  var g = f.analystGrowth5y != null ? f.analystGrowth5y : f.earningsGrowth;
  if (g == null || !isFinite(g)) g = 0.05;
  growthPct = clamp(g * 100, 0, 15); // Graham capped growth contribution

  var Y = 5.0; // proxy for current AAA corporate bond yield (%)
  var intrinsic = (eps * (8.5 + 2 * growthPct) * 4.4) / Y;

  return {
    ok: true,
    name: "Graham Revised Formula",
    intrinsicPerShare: intrinsic,
    assumptions: {
      eps: eps,
      growthPct: growthPct,
      bondYieldPct: Y,
    },
  };
}

// Graham Number: sqrt(22.5 * EPS * BVPS). Max price a defensive investor should pay.
function grahamNumber(f) {
  var eps = f.trailingEps;
  var bvps = f.bookValuePerShare;
  if (eps == null || eps <= 0 || bvps == null || bvps <= 0) {
    return {
      ok: false,
      reason: "Graham Number requires positive EPS and book value",
    };
  }
  var val = Math.sqrt(22.5 * eps * bvps);
  return {
    ok: true,
    name: "Graham Number (defensive ceiling)",
    intrinsicPerShare: val,
    assumptions: { eps: eps, bookValuePerShare: bvps },
  };
}

// Earnings Power Value: EPS / required return. Bruce Greenwald style, no growth assumed.
function epvModel(f) {
  var eps = f.trailingEps;
  if (eps == null || eps <= 0) {
    return { ok: false, reason: "EPV requires positive EPS" };
  }
  var r = 0.09;
  if (f.beta && f.beta > 0) r = clamp(0.04 + f.beta * 0.05, 0.07, 0.12);
  return {
    ok: true,
    name: "Earnings Power Value (no growth)",
    intrinsicPerShare: eps / r,
    assumptions: { eps: eps, discountRate: r },
  };
}

// PEG-style fair P/E: if growth is g% then fair P/E = g. FV = EPS * g.
function pegFairValue(f) {
  var eps = f.trailingEps;
  if (eps == null || eps <= 0) {
    return { ok: false, reason: "PEG fair value requires positive EPS" };
  }
  var g = f.analystGrowth5y != null ? f.analystGrowth5y : f.earningsGrowth;
  if (g == null || g <= 0) {
    return { ok: false, reason: "No positive growth rate" };
  }
  var growthPct = clamp(g * 100, 5, 25);
  return {
    ok: true,
    name: "PEG Fair Value (Lynch)",
    intrinsicPerShare: eps * growthPct,
    assumptions: { eps: eps, growthPct: growthPct },
  };
}

// Dividend Discount Model (Gordon growth), for dividend payers.
function ddmModel(f) {
  var div = f.dividendRate;
  if (div == null || div <= 0) {
    return { ok: false, reason: "Not a dividend payer" };
  }
  var r = 0.09;
  if (f.beta && f.beta > 0) r = clamp(0.04 + f.beta * 0.05, 0.07, 0.12);
  var g = 0.03;
  if (f.earningsGrowth != null && f.earningsGrowth > 0) {
    g = clamp(f.earningsGrowth, 0, r - 0.01);
  }
  if (r - g <= 0.005) g = r - 0.01;
  var val = (div * (1 + g)) / (r - g);
  return {
    ok: true,
    name: "Dividend Discount Model",
    intrinsicPerShare: val,
    assumptions: { dividend: div, growth: g, discountRate: r },
  };
}

function runAllModels(f) {
  var models = [
    dcfModel(f),
    grahamFormula(f),
    grahamNumber(f),
    epvModel(f),
    pegFairValue(f),
    ddmModel(f),
  ];

  // Weighted blend. DCF carries the most weight since it uses forward cash flows.
  var weights = {
    "Discounted Cash Flow (10yr, 2-stage)": 3,
    "Graham Revised Formula": 1.5,
    "Graham Number (defensive ceiling)": 1,
    "Earnings Power Value (no growth)": 1.5,
    "PEG Fair Value (Lynch)": 1,
    "Dividend Discount Model": 1,
  };

  var weightedSum = 0;
  var weightTotal = 0;
  for (var i = 0; i < models.length; i++) {
    var m = models[i];
    if (!m.ok) continue;
    if (m.intrinsicPerShare == null || !isFinite(m.intrinsicPerShare))
      continue;
    if (m.intrinsicPerShare <= 0) continue;
    var w = weights[m.name] || 1;
    weightedSum += w * m.intrinsicPerShare;
    weightTotal += w;
  }
  var blended = weightTotal > 0 ? weightedSum / weightTotal : null;

  return { models: models, blendedIntrinsic: blended };
}

// Optional Claude-generated qualitative thesis.
async function generateThesis(f, valuation) {
  var apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return null;

  var rows = [];
  function add(k, v) {
    rows.push(k + ": " + v);
  }
  add("Ticker", f.ticker);
  add("Name", f.name);
  add("Sector", f.sector || "n/a");
  add("Industry", f.industry || "n/a");
  add("Currency", f.currency);
  add("Current price", f.currentPrice);
  add("Market cap", f.marketCap);
  add("Trailing EPS", f.trailingEps);
  add("Forward EPS", f.forwardEps);
  add("Trailing P/E", f.trailingPE);
  add("Forward P/E", f.forwardPE);
  add("Book value/share", f.bookValuePerShare);
  add("Beta", f.beta);
  add("Dividend yield", f.dividendYield);
  add("Revenue growth (yoy)", f.revenueGrowth);
  add("Earnings growth (yoy)", f.earningsGrowth);
  add("Analyst 5y growth", f.analystGrowth5y);
  add("Free cash flow", f.freeCashflow);
  add("Total cash", f.totalCash);
  add("Total debt", f.totalDebt);
  add("Return on equity", f.returnOnEquity);
  add("Profit margins", f.profitMargins);

  var modelLines = valuation.models
    .map(function (m) {
      if (!m.ok) return "- " + (m.name || "model") + ": n/a (" + m.reason + ")";
      return "- " + m.name + ": " + m.intrinsicPerShare.toFixed(2);
    })
    .join("\n");

  var blended =
    valuation.blendedIntrinsic != null
      ? valuation.blendedIntrinsic.toFixed(2)
      : "n/a";

  var systemPrompt =
    "You are a careful sell-side equity analyst. Given live fundamentals " +
    "and multiple intrinsic-value model outputs, produce a concise valuation " +
    "thesis. Be balanced, cite the numbers, and avoid hype. 4-7 short " +
    "paragraphs. Finish with a one-line verdict: UNDERVALUED, FAIRLY VALUED, " +
    "or OVERVALUED, and the % margin of safety vs current price. " +
    "Always include the disclaimer 'Not investment advice.' at the end.";

  var userPrompt =
    "FUNDAMENTALS\n" +
    rows.join("\n") +
    "\n\nMODEL OUTPUTS (per-share intrinsic value)\n" +
    modelLines +
    "\nBlended intrinsic value: " +
    blended +
    "\nCurrent price: " +
    f.currentPrice +
    "\n\nWrite the thesis now.";

  try {
    var res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: "claude-opus-4-6",
        max_tokens: 900,
        system: systemPrompt,
        messages: [{ role: "user", content: userPrompt }],
      }),
    });
    if (!res.ok) {
      var t = await res.text();
      console.error("Claude thesis failed:", res.status, t);
      return null;
    }
    var data = await res.json();
    if (data && data.content && data.content[0] && data.content[0].text) {
      return data.content[0].text.trim();
    }
    return null;
  } catch (e) {
    console.error("Claude thesis error:", e);
    return null;
  }
}

function sanitizeTicker(input) {
  if (!input) return null;
  var t = String(input).trim().toUpperCase();
  // Allow letters, digits, dot, dash (e.g. BRK.B, RY.TO)
  if (!/^[A-Z0-9.\-]{1,12}$/.test(t)) return null;
  return t;
}

async function handle(ticker) {
  var clean = sanitizeTicker(ticker);
  if (!clean) {
    return new Response(JSON.stringify({ error: "Invalid ticker symbol" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    var raw = await fetchYahoo(clean);
    var fundamentals = extractFundamentals(raw);
    var valuation = runAllModels(fundamentals);

    var marginOfSafety = null;
    if (
      valuation.blendedIntrinsic != null &&
      fundamentals.currentPrice != null &&
      fundamentals.currentPrice > 0
    ) {
      marginOfSafety =
        (valuation.blendedIntrinsic - fundamentals.currentPrice) /
        fundamentals.currentPrice;
    }

    var verdict = "unknown";
    if (marginOfSafety != null) {
      if (marginOfSafety > 0.2) verdict = "undervalued";
      else if (marginOfSafety < -0.2) verdict = "overvalued";
      else verdict = "fairly valued";
    }

    var thesis = await generateThesis(fundamentals, valuation);

    return new Response(
      JSON.stringify({
        ticker: clean,
        fundamentals: fundamentals,
        valuation: valuation,
        blendedIntrinsic: valuation.blendedIntrinsic,
        marginOfSafety: marginOfSafety,
        verdict: verdict,
        thesis: thesis,
        disclaimer:
          "Educational tool only. Not investment advice. Valuations rely on publicly reported financials and simple models; actual fair value depends on factors these models do not capture.",
      }),
      { headers: { "Content-Type": "application/json" } }
    );
  } catch (e) {
    return new Response(
      JSON.stringify({ error: e.message || "Valuation failed" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
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
