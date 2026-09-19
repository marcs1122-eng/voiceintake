"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DishArt from "./DishArt";
import {
  business, collections, products, trends, occasions, look, gallery, videos, about, testimonials, faqs, footerLinks,
} from "./content";

const CART_KEY = "tabletop-stop-cart";
const PAGE_SIZE = 8;
const money = (n) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
const byId = Object.fromEntries(products.map((p) => [p.id, p]));
const collectionName = (id) => (collections.find((c) => c.id === id) || {}).name || "";

/* ───────────── small helpers ───────────── */

function Media({ image, hoverImage, art, hoverArt, alt, ratio = "" }) {
  const hasHover = Boolean(hoverImage || hoverArt);
  return (
    <div className={`tt-media ${ratio}`}>
      <div className="layer base">{image ? <img src={image} alt={alt || ""} loading="lazy" /> : <DishArt art={art} title={alt} />}</div>
      {hasHover && (
        <div className="layer hover" aria-hidden="true">
          {hoverImage ? <img src={hoverImage} alt="" loading="lazy" /> : <DishArt art={hoverArt} />}
        </div>
      )}
    </div>
  );
}

function Icon({ name }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round", viewBox: "0 0 24 24" };
  switch (name) {
    case "bag": return <svg {...common}><path d="M6 8h12l1 13H5L6 8z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></svg>;
    case "play": return <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>;
    case "mail": return <svg {...common}><rect x="3" y="5" width="18" height="14" rx="1" /><path d="m3 7 9 6 9-6" /></svg>;
    case "phone": return <svg {...common}><path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" /></svg>;
    case "pin": return <svg {...common}><path d="M12 21s7-6.5 7-12a7 7 0 1 0-14 0c0 5.5 7 12 7 12z" /><circle cx="12" cy="9" r="2.5" /></svg>;
    case "instagram": return <svg {...common}><rect x="3" y="3" width="18" height="18" rx="5" /><circle cx="12" cy="12" r="4" /><circle cx="17.5" cy="6.5" r=".8" fill="currentColor" /></svg>;
    case "facebook": return <svg {...common}><path d="M14 8h3V4h-3a4 4 0 0 0-4 4v3H7v4h3v6h4v-6h3l1-4h-4V8z" /></svg>;
    case "pinterest": return <svg {...common}><circle cx="12" cy="12" r="9" /><path d="M10 21l2-8m-1.5-2a2.5 2.5 0 1 1 4 2c-.5.5-1.5.8-2.3.6" /></svg>;
    default: return null;
  }
}

function ProductCard({ p, onAdd }) {
  return (
    <article className="tt-card">
      <div className="tt-card-media">
        <Media image={p.image} hoverImage={p.hoverImage} art={p.art} hoverArt={p.hoverArt} alt={p.name} />
        {p.badge && <span className="tt-badge">{p.badge}</span>}
        <button type="button" className="tt-quick" onClick={() => onAdd(p)}>Add to bag</button>
      </div>
      <div className="tt-card-body">
        <h3 className="tt-card-name">{p.name}</h3>
        <div className="tt-card-price">
          <span className={p.compareAt ? "sale" : ""}>{money(p.price)}</span>
          {p.compareAt && <s>{money(p.compareAt)}</s>}
        </div>
      </div>
    </article>
  );
}

/* ───────────── cart state ───────────── */

function useCart() {
  const [items, setItems] = useState([]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(CART_KEY);
      if (raw) setItems(JSON.parse(raw).filter((i) => byId[i.id]));
    } catch (e) { /* storage unavailable */ }
    setReady(true);
  }, []);
  useEffect(() => {
    if (!ready) return;
    try { window.localStorage.setItem(CART_KEY, JSON.stringify(items)); } catch (e) { /* ignore */ }
  }, [items, ready]);

  const add = useCallback((id, qty = 1) => {
    setItems((cur) => {
      const found = cur.find((i) => i.id === id);
      if (found) return cur.map((i) => (i.id === id ? { ...i, qty: i.qty + qty } : i));
      return [...cur, { id, qty }];
    });
  }, []);
  const setQty = useCallback((id, qty) => {
    setItems((cur) => (qty <= 0 ? cur.filter((i) => i.id !== id) : cur.map((i) => (i.id === id ? { ...i, qty } : i))));
  }, []);
  const clear = useCallback(() => setItems([]), []);
  const count = items.reduce((n, i) => n + i.qty, 0);
  const subtotal = items.reduce((n, i) => n + i.qty * byId[i.id].price, 0);
  return { items, add, setQty, clear, count, subtotal };
}

/* ───────────── forms ───────────── */

async function submitForm(subject, fields) {
  if (business.formEndpoint) {
    const res = await fetch(business.formEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ subject, ...fields }),
    });
    if (!res.ok) throw new Error("Form submission failed");
    return "sent";
  }
  const body = Object.entries(fields).map(([k, v]) => `${k}: ${v}`).join("\n");
  window.location.href = `mailto:${business.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  return "mailto";
}

/* ───────────── sections ───────────── */

function Header({ count, onCart }) {
  const [open, setOpen] = useState(false);
  const links = [
    ["New Arrivals", "#new"], ["Shop", "#shop"], ["Gallery", "#gallery"], ["Videos", "#videos"], ["Our Story", "#about"], ["Showroom", "#showroom"],
  ];
  return (
    <>
      <div className="tt-announce">{business.announcement}</div>
      <header className="tt-header">
        <div className="tt-wrap tt-header-inner">
          <button type="button" className="tt-burger" aria-label="Menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            <span /><span /><span />
          </button>
          <nav className="tt-nav" aria-label="Primary">
            {links.slice(0, 3).map(([l, h]) => <a key={h} href={h}>{l}</a>)}
          </nav>
          <a className="tt-logo" href="#top">
            {business.name}
            <small>Est. at home</small>
          </a>
          <div className="tt-header-actions">
            <nav className="tt-nav" aria-label="Secondary">
              {links.slice(3).map(([l, h]) => <a key={h} href={h}>{l}</a>)}
            </nav>
            <button type="button" className="tt-bag" onClick={onCart} aria-label={`Open bag, ${count} items`}>
              <Icon name="bag" />
              <span className="lbl">Bag</span>
              {count > 0 && <span className="tt-bag-count">{count}</span>}
            </button>
          </div>
        </div>
        <div className={`tt-mobile-nav ${open ? "open" : ""}`}>
          <div className="tt-wrap">
            {links.map(([l, h]) => <a key={h} href={h} onClick={() => setOpen(false)}>{l}</a>)}
          </div>
        </div>
      </header>
    </>
  );
}

function Hero() {
  return (
    <section className="tt-hero" id="top">
      <div className="tt-hero-copy">
        <span className="tt-label">{business.season} Collection</span>
        <h1>Set a table <em>worth lingering at</em></h1>
        <p>
          Hand-picked dinnerware, serveware and table accents, chosen at our own table and offered from our home showroom to yours.
        </p>
        <div className="tt-hero-ctas">
          <a className="tt-btn" href="#new">Shop New Arrivals</a>
          <a className="tt-btn outline" href="#showroom">Book a Showroom Visit</a>
        </div>
      </div>
      <div className="tt-hero-media">
        {look.image ? <img src={look.image} alt="A styled fall table" /> : <DishArt art={{ pattern: "table", base: "#EAD9C4", accent: "#B85F3A" }} title="A styled fall table" />}
      </div>
    </section>
  );
}

function TabbedProducts({ onAdd }) {
  const tabs = [["new", "New Arrivals"], ["best", "Best Sellers"], ["gift", "Gift Sets"]];
  const [tab, setTab] = useState("new");
  const list = products.filter((p) => (p.tags || []).includes(tab));
  return (
    <section className="tt-section" id="new">
      <div className="tt-wrap">
        <div className="tt-tabs" role="tablist">
          {tabs.map(([id, label]) => (
            <button key={id} role="tab" aria-selected={tab === id} type="button" className={`tt-tab ${tab === id ? "on" : ""}`} onClick={() => setTab(id)}>{label}</button>
          ))}
        </div>
        <div className="tt-row">
          {list.map((p) => <ProductCard key={p.id} p={p} onAdd={onAdd} />)}
        </div>
        <div className="tt-after"><a className="tt-link" href="#shop">Shop All</a></div>
      </div>
    </section>
  );
}

function Trends({ onCategory }) {
  return (
    <section className="tt-section soft">
      <div className="tt-wrap">
        <div className="tt-head tt-center">
          <span className="tt-label">{trends.eyebrow}</span>
          <h2 className="tt-h2">{trends.heading}</h2>
          <p className="tt-lede">{trends.blurb}</p>
        </div>
        <div className="tt-tiles">
          {trends.tiles.map((t) => (
            <button type="button" className="tt-tile" key={t.label} onClick={() => onCategory(t.collection)}>
              <Media image={t.image} art={t.art} alt={t.label} ratio="portrait" />
              <span className="tt-tile-label">{t.label}</span>
              <span className="tt-tile-sub">Shop the edit</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function Categories({ onCategory }) {
  return (
    <section className="tt-section" id="categories">
      <div className="tt-wrap">
        <div className="tt-head tt-center">
          <h2 className="tt-h2">Shop by Category</h2>
        </div>
        <div className="tt-tiles six">
          {collections.map((c) => (
            <button type="button" className="tt-tile" key={c.id} onClick={() => onCategory(c.id)}>
              <Media art={c.art} alt={c.name} />
              <span className="tt-tile-label">{c.name}</span>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function Shop({ filter, setFilter, onAdd }) {
  const [sort, setSort] = useState("featured");
  const [shown, setShown] = useState(PAGE_SIZE);
  useEffect(() => { setShown(PAGE_SIZE); }, [filter, sort]);
  const list = useMemo(() => {
    let l = filter === "all" ? products.slice() : products.filter((p) => p.collection === filter);
    if (sort === "low") l.sort((a, b) => a.price - b.price);
    if (sort === "high") l.sort((a, b) => b.price - a.price);
    if (sort === "az") l.sort((a, b) => a.name.localeCompare(b.name));
    return l;
  }, [filter, sort]);
  const visible = list.slice(0, shown);
  return (
    <section className="tt-section" id="shop">
      <div className="tt-wrap">
        <div className="tt-shop-head">
          <span className="tt-label">The collection</span>
          <h2>{filter === "all" ? `${business.season}` : collectionName(filter)}</h2>
          <p className="tt-lede">
            Fresh glazes, richer colorways and the hand-finished details we love. Every piece is in the showroom now and ready to ship or pick up.
          </p>
        </div>
        <div className="tt-shop-bar">
          <div className="tt-filters" role="tablist" aria-label="Filter by category">
            <button type="button" className={`tt-filter ${filter === "all" ? "on" : ""}`} onClick={() => setFilter("all")}>All</button>
            {collections.map((c) => (
              <button key={c.id} type="button" className={`tt-filter ${filter === c.id ? "on" : ""}`} onClick={() => setFilter(c.id)}>{c.name}</button>
            ))}
          </div>
          <label className="tt-sort">
            Sort by
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="featured">Featured</option>
              <option value="low">Price, low to high</option>
              <option value="high">Price, high to low</option>
              <option value="az">Alphabetically, A–Z</option>
            </select>
          </label>
        </div>
        <div className="tt-grid">
          {visible.map((p) => <ProductCard key={p.id} p={p} onAdd={onAdd} />)}
        </div>
        <div className="tt-after">
          <p className="tt-count">Showing {visible.length} of {list.length}</p>
          {shown < list.length && (
            <button type="button" className="tt-btn outline" onClick={() => setShown((s) => s + PAGE_SIZE)}>Load more</button>
          )}
        </div>
        <div className="tt-shop-note">
          <div><b>Pickup</b>{business.shipping.localPickup}</div>
          <div><b>Shipping</b>{business.shipping.flatRate}</div>
          <div><b>Payment</b>{business.paymentNote}</div>
        </div>
      </div>
    </section>
  );
}

function ShopTheLook({ onAdd }) {
  const items = look.productIds.map((id) => byId[id]).filter(Boolean);
  return (
    <section className="tt-section soft">
      <div className="tt-wrap tt-look">
        <Media image={look.image} art={look.art} alt={look.heading} ratio="landscape" />
        <div>
          <span className="tt-label">{look.eyebrow}</span>
          <h2 className="tt-h2">{look.heading}</h2>
          <p className="tt-lede">{look.blurb}</p>
          <div className="tt-look-list">
            {items.map((p) => (
              <div className="tt-look-item" key={p.id}>
                <Media image={p.image} art={p.art} alt={p.name} />
                <div>
                  <h4>{p.name}</h4>
                  <span>{money(p.price)}</span>
                </div>
                <button type="button" className="tt-look-add" onClick={() => onAdd(p)}>Add</button>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 24 }}>
            <button type="button" className="tt-btn" onClick={() => items.forEach((p) => onAdd(p, true))}>Add the whole look</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function Occasions({ onCategory }) {
  return (
    <section className="tt-section">
      <div className="tt-wrap">
        <div className="tt-head row">
          <div>
            <span className="tt-label">Set the scene</span>
            <h2 className="tt-h2">Occasions</h2>
          </div>
          <a className="tt-link" href="#showroom">Plan it with us</a>
        </div>
        <div className="tt-scroller">
          {occasions.map((o) => (
            <button type="button" className="tt-tile" key={o.label} onClick={() => onCategory("all")}>
              <div style={{ position: "relative" }}>
                <Media image={o.image} art={o.art} alt={o.label} ratio="portrait" />
                <div className="tt-tile-caption">{o.label}<small>Shop the table</small></div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function Gallery() {
  const [idx, setIdx] = useState(-1);
  const close = () => setIdx(-1);
  const step = useCallback((d) => setIdx((i) => (i + d + gallery.length) % gallery.length), []);
  useEffect(() => {
    if (idx < 0) return;
    const onKey = (e) => { if (e.key === "Escape") close(); if (e.key === "ArrowRight") step(1); if (e.key === "ArrowLeft") step(-1); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [idx, step]);
  const g = gallery[idx];
  return (
    <section className="tt-section" id="gallery">
      <div className="tt-wrap">
        <div className="tt-head tt-center">
          <span className="tt-label">Inspiration</span>
          <h2 className="tt-h2">Tables We&apos;ve Set</h2>
          <p className="tt-lede">From the showroom and from our customers&apos; homes. Tag us to be featured.</p>
        </div>
        <div className="tt-gallery">
          {gallery.map((item, i) => (
            <button type="button" className="tt-gitem" key={item.id} onClick={() => setIdx(i)} aria-label={`Open: ${item.caption}`}>
              <figure style={{ margin: 0, height: "100%" }}>
                <Media image={item.image} art={item.art} alt={item.caption} />
                <figcaption>{item.caption}</figcaption>
              </figure>
            </button>
          ))}
        </div>
      </div>
      {g && (
        <div className="tt-lightbox" role="dialog" aria-modal="true" aria-label={g.caption} onClick={close}>
          <button type="button" className="tt-lightbox-x" aria-label="Close" onClick={close}>×</button>
          <button type="button" className="tt-lightbox-arrow prev" aria-label="Previous" onClick={(e) => { e.stopPropagation(); step(-1); }}>‹</button>
          <button type="button" className="tt-lightbox-arrow next" aria-label="Next" onClick={(e) => { e.stopPropagation(); step(1); }}>›</button>
          <div className="tt-lightbox-inner" onClick={(e) => e.stopPropagation()}>
            <Media image={g.image} art={g.art} alt={g.caption} ratio="landscape" />
            <div className="tt-lightbox-cap">{g.caption}</div>
          </div>
        </div>
      )}
    </section>
  );
}

function VideoFrame({ v }) {
  if (v.youtubeId) {
    return <iframe src={`https://www.youtube-nocookie.com/embed/${v.youtubeId}`} title={v.title} loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowFullScreen />;
  }
  if (v.src) return <video src={v.src} controls playsInline preload="metadata" />;
  return (
    <div className="tt-video-soon">
      <div>
        <div className="play"><Icon name="play" /></div>
        <small>Video coming soon</small>
      </div>
    </div>
  );
}

function Videos() {
  const [first, ...rest] = videos;
  return (
    <section className="tt-section soft" id="videos">
      <div className="tt-wrap">
        <div className="tt-head row">
          <div>
            <span className="tt-label">Watch</span>
            <h2 className="tt-h2">Inside Tabletop Stop</h2>
          </div>
          <a className="tt-link" href={business.instagram} target="_blank" rel="noreferrer">Follow along</a>
        </div>
        <div className="tt-videos">
          <div className="tt-video">
            <div className="tt-video-frame"><VideoFrame v={first} /></div>
            <div className="tt-video-body"><h3>{first.title}</h3><p>{first.blurb}</p></div>
          </div>
          <div className="tt-video-side">
            {rest.map((v) => (
              <div className="tt-video" key={v.id}>
                <div className="tt-video-frame"><VideoFrame v={v} /></div>
                <div className="tt-video-body"><h3>{v.title}</h3><p>{v.blurb}</p></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function About() {
  return (
    <section className="tt-section" id="about">
      <div className="tt-wrap tt-about">
        <Media image={about.image} art={about.art} alt="Inside the Tabletop Stop showroom" ratio="portrait" />
        <div className="tt-about-copy">
          <span className="tt-label">{about.eyebrow}</span>
          <h2 className="tt-h2">{about.heading}</h2>
          {about.paragraphs.map((p, i) => <p key={i}>{p}</p>)}
          <div className="tt-signature">{about.signature}</div>
        </div>
      </div>
    </section>
  );
}

function Showroom() {
  const [state, setState] = useState("idle");
  const [reason, setReason] = useState("visit");
  const onSubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const fields = Object.fromEntries([...f.entries()].map(([k, v]) => [k, String(v)]));
    setState("sending");
    try {
      const how = await submitForm(`Tabletop Stop — ${reason === "visit" ? "Showroom visit request" : reason === "registry" ? "Registry inquiry" : "Question"}`, fields);
      setState(how);
      if (how === "sent") e.target.reset();
    } catch (err) { setState("error"); }
  };
  return (
    <section className="tt-section soft" id="showroom">
      <div className="tt-wrap tt-showroom">
        <div>
          <span className="tt-label">Visit us</span>
          <h2 className="tt-h2">The Home Showroom</h2>
          <p className="tt-lede">
            Every piece on the site is out on real tables in our home, so you can see how it layers, feel the weight of a plate and try it against your own linens. {business.showroomNote}
          </p>
          <div className="tt-hours">
            {business.hours.map((h) => <div key={h.day}><span>{h.day}</span><span>{h.time}</span></div>)}
          </div>
          <ul className="tt-expect">
            <li>Private, one-on-one appointments, usually about an hour</li>
            <li>Take pieces home the same day, or have them wrapped and shipped</li>
            <li>Registry and full-table styling help at no charge</li>
          </ul>
          <div className="tt-contact-list" id="contact">
            <a href={`mailto:${business.email}`}><Icon name="mail" />{business.email}</a>
            <a href={business.phoneHref}><Icon name="phone" />{business.phone}</a>
            <a href="#showroom"><Icon name="pin" />{business.city} · address shared on booking</a>
          </div>
        </div>
        <form className="tt-form" onSubmit={onSubmit}>
          <h3>Book a visit or say hello</h3>
          <p className="hint">We reply within one business day.</p>
          <div className="tt-field">
            <label htmlFor="tt-reason">I&apos;d like to</label>
            <select id="tt-reason" name="reason" value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="visit">Book a showroom visit</option>
              <option value="registry">Set up a registry</option>
              <option value="question">Ask a question</option>
            </select>
          </div>
          <div className="tt-two">
            <div className="tt-field"><label htmlFor="tt-name">Name</label><input id="tt-name" name="name" required autoComplete="name" /></div>
            <div className="tt-field"><label htmlFor="tt-phone">Phone</label><input id="tt-phone" name="phone" type="tel" autoComplete="tel" /></div>
          </div>
          <div className="tt-field"><label htmlFor="tt-email">Email</label><input id="tt-email" name="email" type="email" required autoComplete="email" /></div>
          {reason === "visit" && (
            <div className="tt-two">
              <div className="tt-field"><label htmlFor="tt-date">Preferred day</label><input id="tt-date" name="preferred_day" type="date" /></div>
              <div className="tt-field"><label htmlFor="tt-time">Preferred time</label><input id="tt-time" name="preferred_time" placeholder="e.g. late morning" /></div>
            </div>
          )}
          <div className="tt-field"><label htmlFor="tt-msg">Notes</label><textarea id="tt-msg" name="message" placeholder="What are you shopping for? How many are you setting the table for?" /></div>
          <button type="submit" className="tt-btn block" disabled={state === "sending"}>{state === "sending" ? "Sending…" : "Send request"}</button>
          {state === "sent" && <div className="tt-form-ok">Thank you. We&apos;ll be in touch within one business day.</div>}
          {state === "mailto" && <div className="tt-form-ok">Your email app should have opened with the details filled in. If it didn&apos;t, email us at {business.email}.</div>}
          {state === "error" && <div className="tt-form-ok">Something went wrong. Please email us directly at {business.email}.</div>}
        </form>
      </div>
    </section>
  );
}

function Testimonials() {
  return (
    <section className="tt-section">
      <div className="tt-wrap">
        <div className="tt-head tt-center"><span className="tt-label">Kind words</span></div>
        <div className="tt-quotes">
          {testimonials.map((t) => (
            <figure className="tt-quote" key={t.name} style={{ margin: 0 }}>
              <div className="tt-stars" aria-label="Five stars">★★★★★</div>
              <p>“{t.quote}”</p>
              <figcaption><b>{t.name}</b><span>{t.detail}</span></figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

function Faq() {
  return (
    <section className="tt-section soft" id="faq">
      <div className="tt-wrap">
        <div className="tt-head tt-center">
          <span className="tt-label">Good to know</span>
          <h2 className="tt-h2">Questions, Answered</h2>
        </div>
        <div className="tt-faq">
          {faqs.map((f) => (
            <details key={f.q}><summary>{f.q}</summary><p>{f.a}</p></details>
          ))}
        </div>
      </div>
    </section>
  );
}

function Newsletter() {
  const [done, setDone] = useState(false);
  const onSubmit = async (e) => {
    e.preventDefault();
    const email = new FormData(e.currentTarget).get("email");
    try { await submitForm("Tabletop Stop — newsletter signup", { email: String(email) }); } catch (err) { /* fall through */ }
    setDone(true);
  };
  return (
    <section className="tt-newsletter">
      <div className="tt-wrap">
        <span className="tt-label">Endless entertaining</span>
        <h2>Enjoy {business.newsletterOffer} off your first order</h2>
        <p>Sign up for new arrivals, table-setting inspiration and showroom open days. No more than twice a month.</p>
        {done ? (
          <p><b>Welcome to the table.</b> Your code is on its way.</p>
        ) : (
          <form className="tt-news-form" onSubmit={onSubmit}>
            <input type="email" name="email" required placeholder="E-mail" aria-label="Email address" />
            <button type="submit" className="tt-btn">Subscribe</button>
          </form>
        )}
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="tt-footer">
      <div className="tt-wrap">
        <div className="tt-footer-grid">
          <div className="tt-footer-brand">
            <div className="tt-logo">{business.name}</div>
            <p>{business.tagline} Hand-picked pieces from our home showroom in {business.city}, shipped anywhere in the continental US.</p>
            <div className="tt-socials">
              <a href={business.instagram} target="_blank" rel="noreferrer" aria-label="Instagram"><Icon name="instagram" /></a>
              <a href={business.facebook} target="_blank" rel="noreferrer" aria-label="Facebook"><Icon name="facebook" /></a>
              <a href={business.pinterest} target="_blank" rel="noreferrer" aria-label="Pinterest"><Icon name="pinterest" /></a>
            </div>
          </div>
          {Object.entries(footerLinks).map(([title, links]) => (
            <div key={title}>
              <h4>{title}</h4>
              <ul>{links.map((l) => <li key={l.label}><a href={l.href}>{l.label}</a></li>)}</ul>
            </div>
          ))}
        </div>
        <div className="tt-footer-bottom">
          <span>© {new Date().getFullYear()} {business.name}. All rights reserved.</span>
          <span>{business.email} · {business.phone}</span>
        </div>
      </div>
    </footer>
  );
}

/* ───────────── cart drawer ───────────── */

function CartDrawer({ cart, open, onClose }) {
  const [method, setMethod] = useState("pickup");
  const [state, setState] = useState("idle");
  const firstField = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [open, onClose]);
  if (!open) return null;

  const shipping = method === "ship" ? (cart.subtotal >= 150 || cart.subtotal === 0 ? 0 : 12) : 0;
  const lines = cart.items.map((i) => byId[i.id]);
  const allBuyable = lines.length > 0 && lines.every((p) => p.buyUrl);

  const onSubmit = async (e) => {
    e.preventDefault();
    const f = Object.fromEntries([...new FormData(e.currentTarget).entries()].map(([k, v]) => [k, String(v)]));
    const orderLines = cart.items.map((i) => `${i.qty} × ${byId[i.id].name} — ${money(byId[i.id].price * i.qty)}`).join("\n");
    const fields = {
      ...f,
      fulfillment: method === "ship" ? "Ship to me" : "Pick up at the showroom",
      order: `\n${orderLines}\n\nSubtotal: ${money(cart.subtotal)}${method === "ship" ? `\nShipping: ${shipping ? money(shipping) : "Free"}` : ""}\nTotal: ${money(cart.subtotal + shipping)}`,
    };
    setState("sending");
    try {
      const how = await submitForm(`Tabletop Stop — Order request from ${f.name}`, fields);
      setState(how);
      if (how === "sent") cart.clear();
    } catch (err) { setState("error"); }
  };

  return (
    <>
      <div className="tt-scrim" onClick={onClose} />
      <aside className="tt-drawer" role="dialog" aria-modal="true" aria-label="Your bag">
        <div className="tt-drawer-head">
          <h3>Your Bag ({cart.count})</h3>
          <button type="button" className="tt-drawer-x" aria-label="Close bag" onClick={onClose}>×</button>
        </div>
        <div className="tt-drawer-body">
          {lines.length === 0 ? (
            <div className="tt-drawer-empty">
              <div className="tt-serif">Your bag is empty</div>
              <p>Let&apos;s fix that.</p>
              <a className="tt-btn" href="#shop" onClick={onClose}>Shop the collection</a>
            </div>
          ) : (
            cart.items.map((i) => {
              const p = byId[i.id];
              return (
                <div className="tt-line-item" key={i.id}>
                  <Media image={p.image} art={p.art} alt={p.name} />
                  <div>
                    <h4>{p.name}</h4>
                    <div className="price">{money(p.price)}</div>
                    <div className="tt-qty">
                      <button type="button" aria-label="Decrease" onClick={() => cart.setQty(i.id, i.qty - 1)}>−</button>
                      <span>{i.qty}</span>
                      <button type="button" aria-label="Increase" onClick={() => cart.setQty(i.id, i.qty + 1)}>+</button>
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div className="price">{money(p.price * i.qty)}</div>
                    <button type="button" className="tt-remove" style={{ marginTop: 10 }} onClick={() => cart.setQty(i.id, 0)}>Remove</button>
                  </div>
                </div>
              );
            })
          )}
        </div>
        {lines.length > 0 && (
          <form className="tt-drawer-foot" onSubmit={onSubmit}>
            <div className="tt-total"><span>Subtotal</span><span>{money(cart.subtotal)}</span></div>
            {method === "ship" && <div className="tt-total"><span>Shipping</span><span>{shipping ? money(shipping) : "Free"}</span></div>}
            <div className="tt-total big"><span>Total</span><span>{money(cart.subtotal + shipping)}</span></div>
            <div className="tt-radio-row">
              <label className={`tt-radio ${method === "pickup" ? "on" : ""}`}>
                <input type="radio" name="method" checked={method === "pickup"} onChange={() => setMethod("pickup")} />
                <span><b>Showroom pickup</b><small>Free · we&apos;ll arrange a time</small></span>
              </label>
              <label className={`tt-radio ${method === "ship" ? "on" : ""}`}>
                <input type="radio" name="method" checked={method === "ship"} onChange={() => setMethod("ship")} />
                <span><b>Ship to me</b><small>$12 · free over $150</small></span>
              </label>
            </div>
            <div className="tt-two">
              <div className="tt-field"><label htmlFor="bag-name">Name</label><input id="bag-name" name="name" required ref={firstField} autoComplete="name" /></div>
              <div className="tt-field"><label htmlFor="bag-phone">Phone</label><input id="bag-phone" name="phone" type="tel" autoComplete="tel" /></div>
            </div>
            <div className="tt-field"><label htmlFor="bag-email">Email</label><input id="bag-email" name="email" type="email" required autoComplete="email" /></div>
            {method === "ship" && (
              <div className="tt-field"><label htmlFor="bag-address">Shipping address</label><input id="bag-address" name="address" required autoComplete="street-address" /></div>
            )}
            <div className="tt-field"><label htmlFor="bag-notes">Notes (gift message, questions)</label><input id="bag-notes" name="notes" /></div>
            {allBuyable && lines.length === 1 ? (
              <a className="tt-btn block" href={lines[0].buyUrl} target="_blank" rel="noreferrer">Buy now</a>
            ) : (
              <button type="submit" className="tt-btn block" disabled={state === "sending"}>{state === "sending" ? "Sending…" : "Send order request"}</button>
            )}
            {state === "sent" && <div className="tt-form-ok">Order request received. We&apos;ll confirm availability and send a secure payment link shortly.</div>}
            {state === "mailto" && <div className="tt-form-ok">Your email app should have opened with your order filled in. Send it and we&apos;ll reply with a payment link.</div>}
            {state === "error" && <div className="tt-form-ok">Something went wrong. Email us at {business.email} and we&apos;ll sort it out.</div>}
            <p className="tt-fine">No payment is taken on this site. We confirm every order personally and send a secure payment link. {business.paymentNote}</p>
          </form>
        )}
      </aside>
    </>
  );
}

/* ───────────── page ───────────── */

export default function TabletopSite() {
  const cart = useCart();
  const [cartOpen, setCartOpen] = useState(false);
  const [filter, setFilter] = useState("all");
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  const onAdd = useCallback((p, quiet = false) => {
    cart.add(p.id, 1);
    if (quiet) return;
    setToast(`Added to bag: ${p.name}`);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }, [cart]);

  const onCategory = useCallback((id) => {
    setFilter(id);
    const el = document.getElementById("shop");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const closeCart = useCallback(() => setCartOpen(false), []);

  return (
    <div className="tt">
      <Header count={cart.count} onCart={() => setCartOpen(true)} />
      <main>
        <Hero />
        <TabbedProducts onAdd={onAdd} />
        <Trends onCategory={onCategory} />
        <Categories onCategory={onCategory} />
        <Shop filter={filter} setFilter={setFilter} onAdd={onAdd} />
        <ShopTheLook onAdd={onAdd} />
        <Occasions onCategory={onCategory} />
        <Gallery />
        <Videos />
        <About />
        <Showroom />
        <Testimonials />
        <Faq />
        <Newsletter />
      </main>
      <Footer />
      <CartDrawer cart={cart} open={cartOpen} onClose={closeCart} />
      {toast && (
        <div className="tt-toast" role="status">
          <span>{toast}</span>
          <button type="button" onClick={() => { setToast(null); setCartOpen(true); }}>View bag</button>
        </div>
      )}
    </div>
  );
}
