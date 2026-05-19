"use client";

import { useState } from "react";

function fmtMoney(v, currency) {
  if (v == null || !isFinite(v)) return "—";
  var cur = currency || "USD";
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: cur,
      maximumFractionDigits: 2,
    }).format(v);
  } catch (e) {
    return "$" + v.toFixed(2);
  }
}

function fmtBig(v) {
  if (v == null || !isFinite(v)) return "—";
  var abs = Math.abs(v);
  var sign = v < 0 ? "-" : "";
  if (abs >= 1e12) return sign + "$" + (abs / 1e12).toFixed(2) + "T";
  if (abs >= 1e9) return sign + "$" + (abs / 1e9).toFixed(2) + "B";
  if (abs >= 1e6) return sign + "$" + (abs / 1e6).toFixed(2) + "M";
  if (abs >= 1e3) return sign + "$" + (abs / 1e3).toFixed(2) + "K";
  return sign + "$" + abs.toFixed(2);
}

function fmtPct(v) {
  if (v == null || !isFinite(v)) return "—";
  return (v * 100).toFixed(2) + "%";
}

function fmtNum(v, digits) {
  if (v == null || !isFinite(v)) return "—";
  return v.toFixed(digits == null ? 2 : digits);
}

function verdictColor(verdict) {
  if (verdict === "undervalued") return "#16a34a";
  if (verdict === "overvalued") return "#dc2626";
  if (verdict === "fairly valued") return "#ca8a04";
  return "#6b7280";
}

export default function StockValuationPage() {
  var [ticker, setTicker] = useState("");
  var [loading, setLoading] = useState(false);
  var [error, setError] = useState(null);
  var [data, setData] = useState(null);
  var [gex, setGex] = useState(null);
  var [gexError, setGexError] = useState(null);

  async function runValuation(e) {
    if (e) e.preventDefault();
    if (!ticker.trim()) return;
    setLoading(true);
    setError(null);
    setData(null);
    setGex(null);
    setGexError(null);
    var t = ticker.trim();

    var valuationPromise = fetch("/api/stock/valuation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticker: t }),
    })
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, body: j };
        });
      })
      .then(function (out) {
        if (!out.ok) setError(out.body.error || "Valuation failed");
        else setData(out.body);
      })
      .catch(function (err) {
        setError(err.message || "Network error");
      });

    var gexPromise = fetch("/api/stock/gex?ticker=" + encodeURIComponent(t))
      .then(function (r) {
        return r.json().then(function (j) {
          return { ok: r.ok, body: j };
        });
      })
      .then(function (out) {
        if (!out.ok) setGexError(out.body.error || "GEX unavailable");
        else setGex(out.body.gex);
      })
      .catch(function (err) {
        setGexError(err.message || "Network error");
      });

    try {
      await Promise.all([valuationPromise, gexPromise]);
    } finally {
      setLoading(false);
    }
  }

  var f = data && data.fundamentals;
  var v = data && data.valuation;
  var currency = f && f.currency;

  return (
    <main
      style={{
        minHeight: "100vh",
        background:
          "linear-gradient(180deg, #0f172a 0%, #1e293b 100%)",
        color: "#e2e8f0",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        padding: "40px 20px",
      }}
    >
      <div style={{ maxWidth: 920, margin: "0 auto" }}>
        <header style={{ marginBottom: 32 }}>
          <h1
            style={{
              margin: 0,
              fontSize: 34,
              fontWeight: 700,
              background:
                "linear-gradient(90deg, #60a5fa 0%, #a78bfa 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Intrinsic Value Calculator
          </h1>
          <p style={{ margin: "8px 0 0", color: "#94a3b8", fontSize: 15 }}>
            Enter a ticker. I'll pull the latest financials and run DCF,
            Graham, EPV, PEG and DDM models to estimate fair value.
          </p>
        </header>

        <form
          onSubmit={runValuation}
          style={{
            display: "flex",
            gap: 10,
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: 12,
            padding: 12,
            boxShadow: "0 4px 20px rgba(0,0,0,0.2)",
          }}
        >
          <input
            type="text"
            value={ticker}
            onChange={function (e) {
              setTicker(e.target.value.toUpperCase());
            }}
            placeholder="e.g. AAPL, MSFT, BRK.B, NVDA"
            autoFocus
            style={{
              flex: 1,
              background: "#0f172a",
              border: "1px solid #334155",
              borderRadius: 8,
              padding: "14px 16px",
              color: "#f1f5f9",
              fontSize: 18,
              letterSpacing: 1,
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={loading || !ticker.trim()}
            style={{
              background:
                loading || !ticker.trim()
                  ? "#475569"
                  : "linear-gradient(90deg, #3b82f6, #8b5cf6)",
              color: "white",
              border: "none",
              borderRadius: 8,
              padding: "0 28px",
              fontSize: 16,
              fontWeight: 600,
              cursor: loading || !ticker.trim() ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Analyzing…" : "Calculate"}
          </button>
        </form>

        {error && (
          <div
            style={{
              marginTop: 20,
              padding: 16,
              background: "#7f1d1d",
              border: "1px solid #dc2626",
              borderRadius: 10,
              color: "#fecaca",
            }}
          >
            {error}
          </div>
        )}

        {loading && (
          <div
            style={{
              marginTop: 24,
              textAlign: "center",
              color: "#94a3b8",
            }}
          >
            Pulling latest financials and running valuation models…
          </div>
        )}

        {data && f && v && (
          <div style={{ marginTop: 28 }}>
            {/* Header card: name, verdict, intrinsic vs price */}
            <div
              style={{
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: 14,
                padding: 24,
                marginBottom: 20,
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  flexWrap: "wrap",
                  gap: 12,
                }}
              >
                <div>
                  <div style={{ fontSize: 13, color: "#64748b" }}>
                    {f.exchange || ""} · {f.sector || "—"}
                  </div>
                  <h2 style={{ margin: "4px 0 2px", fontSize: 26 }}>
                    {f.name || f.ticker}{" "}
                    <span style={{ color: "#64748b", fontSize: 18 }}>
                      ({f.ticker})
                    </span>
                  </h2>
                  <div style={{ fontSize: 13, color: "#94a3b8" }}>
                    {f.industry || ""}
                  </div>
                </div>
                <div
                  style={{
                    padding: "8px 16px",
                    borderRadius: 999,
                    background: verdictColor(data.verdict),
                    color: "white",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    fontSize: 13,
                    letterSpacing: 0.5,
                  }}
                >
                  {data.verdict}
                </div>
              </div>

              <div
                style={{
                  marginTop: 24,
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
                  gap: 16,
                }}
              >
                <Stat
                  label="Current Price"
                  value={fmtMoney(f.currentPrice, currency)}
                />
                <Stat
                  label="Blended Intrinsic"
                  value={fmtMoney(data.blendedIntrinsic, currency)}
                  highlight
                />
                <Stat
                  label="Margin of Safety"
                  value={
                    data.marginOfSafety != null
                      ? (data.marginOfSafety >= 0 ? "+" : "") +
                        (data.marginOfSafety * 100).toFixed(1) +
                        "%"
                      : "—"
                  }
                  color={
                    data.marginOfSafety == null
                      ? "#e2e8f0"
                      : data.marginOfSafety > 0
                      ? "#34d399"
                      : "#f87171"
                  }
                />
                <Stat label="Market Cap" value={fmtBig(f.marketCap)} />
              </div>
            </div>

            {/* Model breakdown */}
            <Card title="Valuation Models">
              <div style={{ display: "grid", gap: 10 }}>
                {v.models.map(function (m, i) {
                  return (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        padding: "12px 14px",
                        background: "#0f172a",
                        border: "1px solid #1e293b",
                        borderRadius: 8,
                      }}
                    >
                      <div style={{ fontSize: 14, color: "#cbd5e1" }}>
                        {m.name ||
                          (m.ok ? "Model" : "Model unavailable")}
                        {!m.ok && (
                          <div
                            style={{
                              fontSize: 12,
                              color: "#64748b",
                              marginTop: 2,
                            }}
                          >
                            {m.reason}
                          </div>
                        )}
                      </div>
                      <div
                        style={{
                          fontWeight: 700,
                          fontSize: 16,
                          color: m.ok ? "#93c5fd" : "#475569",
                        }}
                      >
                        {m.ok
                          ? fmtMoney(m.intrinsicPerShare, currency)
                          : "n/a"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* FlashAlpha gamma exposure */}
            {(gex || gexError) && (
              <Card title="Gamma Exposure (FlashAlpha)">
                {gexError && (
                  <div style={{ color: "#fca5a5", fontSize: 14 }}>
                    {gexError}
                  </div>
                )}
                {gex && <GexView gex={gex} currency={currency} />}
              </Card>
            )}

            {/* Key fundamentals */}
            <Card title="Key Fundamentals">
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(180px, 1fr))",
                  gap: 14,
                }}
              >
                <Field label="Trailing EPS" value={fmtMoney(f.trailingEps, currency)} />
                <Field label="Forward EPS" value={fmtMoney(f.forwardEps, currency)} />
                <Field label="Trailing P/E" value={fmtNum(f.trailingPE)} />
                <Field label="Forward P/E" value={fmtNum(f.forwardPE)} />
                <Field
                  label="Book Value/Share"
                  value={fmtMoney(f.bookValuePerShare, currency)}
                />
                <Field label="Beta" value={fmtNum(f.beta)} />
                <Field
                  label="Dividend Yield"
                  value={fmtPct(f.dividendYield)}
                />
                <Field label="ROE" value={fmtPct(f.returnOnEquity)} />
                <Field label="Profit Margin" value={fmtPct(f.profitMargins)} />
                <Field label="Revenue Growth" value={fmtPct(f.revenueGrowth)} />
                <Field label="Earnings Growth" value={fmtPct(f.earningsGrowth)} />
                <Field
                  label="Analyst 5y Growth"
                  value={fmtPct(f.analystGrowth5y)}
                />
                <Field label="Revenue (TTM)" value={fmtBig(f.totalRevenue)} />
                <Field label="Net Income (TTM)" value={fmtBig(f.netIncome)} />
                <Field label="Free Cash Flow" value={fmtBig(f.freeCashflow)} />
                <Field label="Total Cash" value={fmtBig(f.totalCash)} />
                <Field label="Total Debt" value={fmtBig(f.totalDebt)} />
                <Field
                  label="Shares Outstanding"
                  value={fmtBig(f.sharesOutstanding)}
                />
              </div>
            </Card>

            {/* AI thesis */}
            {data.thesis && (
              <Card title="Valuation Thesis (AI-generated)">
                <div
                  style={{
                    whiteSpace: "pre-wrap",
                    lineHeight: 1.6,
                    color: "#cbd5e1",
                    fontSize: 15,
                  }}
                >
                  {data.thesis}
                </div>
              </Card>
            )}

            <div
              style={{
                marginTop: 20,
                padding: 14,
                background: "#1e293b",
                border: "1px dashed #475569",
                borderRadius: 10,
                color: "#94a3b8",
                fontSize: 12,
                lineHeight: 1.5,
              }}
            >
              {data.disclaimer}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

function Card(props) {
  return (
    <div
      style={{
        background: "#1e293b",
        border: "1px solid #334155",
        borderRadius: 14,
        padding: 22,
        marginBottom: 20,
      }}
    >
      <h3
        style={{
          margin: "0 0 16px",
          fontSize: 16,
          fontWeight: 600,
          color: "#e2e8f0",
          textTransform: "uppercase",
          letterSpacing: 1,
        }}
      >
        {props.title}
      </h3>
      {props.children}
    </div>
  );
}

function Stat(props) {
  return (
    <div>
      <div
        style={{
          fontSize: 12,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}
      >
        {props.label}
      </div>
      <div
        style={{
          marginTop: 4,
          fontSize: props.highlight ? 26 : 22,
          fontWeight: 700,
          color: props.color || (props.highlight ? "#a78bfa" : "#f1f5f9"),
        }}
      >
        {props.value}
      </div>
    </div>
  );
}

function prettyLabel(key) {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, function (c) {
      return c.toUpperCase();
    });
}

function GexView(props) {
  var gex = props.gex || {};
  var currency = props.currency || "USD";

  // FlashAlpha returns a JSON object. We don't know the exact shape, so
  // surface a few known fields first and render the rest as key/value.
  var known = [
    { key: "spot", label: "Spot", fmt: "money" },
    { key: "gamma_flip", label: "Gamma Flip", fmt: "money" },
    { key: "call_wall", label: "Call Wall", fmt: "money" },
    { key: "put_wall", label: "Put Wall", fmt: "money" },
    { key: "zero_gamma", label: "Zero Gamma", fmt: "money" },
    { key: "total_gex", label: "Total GEX", fmt: "big" },
    { key: "net_gex", label: "Net GEX", fmt: "big" },
    { key: "as_of", label: "As Of", fmt: "raw" },
    { key: "timestamp", label: "Timestamp", fmt: "raw" },
  ];

  function renderValue(v, fmt) {
    if (v == null) return "—";
    if (fmt === "money" && typeof v === "number") return fmtMoney(v, currency);
    if (fmt === "big" && typeof v === "number") return fmtBig(v);
    if (typeof v === "number") return fmtNum(v);
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
  }

  var seen = {};
  var primary = [];
  for (var i = 0; i < known.length; i++) {
    var k = known[i].key;
    if (gex[k] !== undefined && gex[k] !== null) {
      primary.push({ label: known[i].label, value: renderValue(gex[k], known[i].fmt) });
      seen[k] = true;
    }
  }

  var extras = [];
  Object.keys(gex).forEach(function (k) {
    if (seen[k]) return;
    var v = gex[k];
    if (v == null) return;
    if (typeof v === "object" && !Array.isArray(v)) return; // skip nested objects
    extras.push({ label: prettyLabel(k), value: renderValue(v, typeof v === "number" ? "big" : "raw") });
  });

  return (
    <div>
      {primary.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
            gap: 14,
            marginBottom: extras.length ? 16 : 0,
          }}
        >
          {primary.map(function (p, i) {
            return <Field key={i} label={p.label} value={p.value} />;
          })}
        </div>
      )}
      {extras.length > 0 && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: 14,
          }}
        >
          {extras.map(function (p, i) {
            return <Field key={i} label={p.label} value={p.value} />;
          })}
        </div>
      )}
      {primary.length === 0 && extras.length === 0 && (
        <pre
          style={{
            margin: 0,
            color: "#cbd5e1",
            fontSize: 12,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {JSON.stringify(gex, null, 2)}
        </pre>
      )}
    </div>
  );
}

function Field(props) {
  return (
    <div>
      <div style={{ fontSize: 12, color: "#64748b" }}>{props.label}</div>
      <div
        style={{
          fontSize: 15,
          fontWeight: 600,
          color: "#e2e8f0",
          marginTop: 2,
        }}
      >
        {props.value}
      </div>
    </div>
  );
}
