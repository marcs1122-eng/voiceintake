// ─────────────────────────────────────────────────────────────────────────────
//  TABLETOP STOP — SITE CONTENT
//  Everything on the site is driven by this file. Edit the text, prices and
//  lists below; no other file needs to change.
//
//  PHOTOS:  drop image files into  /public/tabletop-stop/  and set
//           image: "/tabletop-stop/your-file.jpg"  (and optionally
//           hoverImage: "..." for the styled shot shown on hover).
//           Items without an image show a drawn placeholder illustration.
//  VIDEOS:  paste a YouTube video ID (the part after ?v=) or a full MP4 URL.
//  SELLING: set  buyUrl  on a product to a Stripe / Square / PayPal payment
//           link and shoppers get a one-click "Buy now". Without it, the cart
//           sends you an order request by email and you reply with an invoice.
// ─────────────────────────────────────────────────────────────────────────────

export const business = {
  name: "Tabletop Stop",
  tagline: "Dishes for the well-dressed table.",
  season: "Fall & Holiday 2026",
  announcement: "Complimentary gift wrapping on every order  ·  Free shipping over $150  ·  Showroom visits by appointment",
  // Contact — replace with the real details
  email: "hello@tabletopstop.com",
  phone: "(000) 000-0000",
  phoneHref: "tel:+10000000000",
  // The showroom is a private home, so only the town is published.
  city: "Your Town, USA",
  showroomNote:
    "Our showroom is our home, so visits are by appointment only. The full address is shared once your visit is confirmed.",
  hours: [
    { day: "Tuesday – Friday", time: "10am – 5pm" },
    { day: "Saturday", time: "10am – 2pm" },
    { day: "Sunday – Monday", time: "Closed" },
  ],
  instagram: "https://instagram.com/",
  facebook: "https://facebook.com/",
  pinterest: "https://pinterest.com/",
  // Optional: a Formspree / Basin / Getform endpoint. When set, the contact and
  // booking forms POST here instead of opening the visitor's email app.
  formEndpoint: "",
  shipping: {
    localPickup: "Free local pickup at the showroom",
    flatRate: "Flat-rate shipping $12, free on orders over $150",
    region: "We ship anywhere in the continental US",
  },
  paymentNote: "We accept all major cards, Venmo, Zelle, and cash at the showroom.",
  newsletterOffer: "10%",
};

// Category tiles ("Shop by Category")
export const collections = [
  { id: "dinner-plates", name: "Dinner Plates", art: { pattern: "rim", base: "#F1E9DD", accent: "#8C5A3C" } },
  { id: "salad-plates", name: "Salad & Dessert", art: { pattern: "scallop", base: "#E3E7DD", accent: "#6F8468" } },
  { id: "bowls", name: "Bowls", art: { pattern: "leaf", base: "#F4EFE6", accent: "#5F7F5B" } },
  { id: "serveware", name: "Serveware", art: { pattern: "wood", base: "#D9BE94", accent: "#7A4E2B" } },
  { id: "glassware", name: "Glassware & Mugs", art: { pattern: "ribbed", base: "#E9CD97", accent: "#A8784A" } },
  { id: "linens", name: "Linens & Decor", art: { pattern: "brass", base: "#F3EDE2", accent: "#A8894F" } },
];

// Product catalogue. `tags` drive the New Arrivals / Best Sellers / Gift Sets tabs.
export const products = [
  {
    id: "harvest-dinner-plate",
    name: "Harvest Dinner Plate in Terracotta & Cream, Set of 4",
    collection: "dinner-plates",
    price: 128,
    description: "A generous 11-inch stoneware plate in a warm speckled cream glaze, finished with a hand-dipped terracotta rim. Dishwasher and microwave safe.",
    tags: ["new", "best"],
    art: { pattern: "rim", base: "#F1E9DD", accent: "#B85F3A" },
    hoverArt: { pattern: "table", base: "#EAD9C4", accent: "#B85F3A" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "sage-scallop-salad",
    name: "Scalloped Salad Plate in Sage, Set of 4",
    collection: "salad-plates",
    price: 88,
    description: "A soft sage glaze with a gently scalloped edge. Lovely on its own or layered over the Harvest dinner plate.",
    tags: ["new", "best"],
    art: { pattern: "scallop", base: "#DCE3D6", accent: "#728A6D" },
    hoverArt: { pattern: "table", base: "#E3E7DD", accent: "#728A6D" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "botanical-oval-platter",
    name: "Botanical Oval Platter in Ivory & Green, 16 in",
    collection: "serveware",
    price: 96,
    description: "Hand-painted leaves trail across a creamy oval platter. Big enough for the roast, pretty enough to leave out.",
    tags: ["new"],
    art: { pattern: "leaf", base: "#F4EFE6", accent: "#5F7F5B" },
    hoverArt: { pattern: "table", base: "#F4EFE6", accent: "#5F7F5B" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "olive-wood-board",
    name: "Olive Wood Serving Board, 18 in",
    collection: "serveware",
    price: 74,
    description: "A single slab of oiled olive wood with a natural live edge. Every board's grain is a little different.",
    tags: ["best", "gift"],
    art: { pattern: "wood", base: "#D9BE94", accent: "#7A4E2B" },
    hoverArt: { pattern: "shelf", base: "#F4EFE6", accent: "#7A4E2B" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "midnight-mugs",
    name: "Slow Morning Mug in Midnight, Set of 2",
    collection: "glassware",
    price: 48,
    description: "Generous 14 oz mugs with a comfortable handle and a glossy midnight glaze that breaks warm at the rim.",
    tags: ["best", "gift"],
    art: { pattern: "dots", base: "#33456B", accent: "#F1E7D6" },
    hoverArt: { pattern: "shelf", base: "#F4EFE6", accent: "#33456B" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "amber-ribbed-tumblers",
    name: "Ribbed Tumbler in Amber, Set of 4",
    collection: "glassware",
    price: 62,
    description: "Softly ribbed glass in a honey amber tint. Catches the candlelight beautifully at dinner.",
    tags: ["new", "gift"],
    art: { pattern: "ribbed", base: "#E9CD97", accent: "#A8784A" },
    hoverArt: { pattern: "table", base: "#F1E9DD", accent: "#A8784A" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "linen-napkins-oat",
    name: "Washed Linen Napkin in Oatmeal, Set of 6",
    collection: "linens",
    price: 54,
    description: "Stonewashed European linen that only gets softer and never needs ironing.",
    tags: ["best"],
    art: { pattern: "linen", base: "#EAE3D6", accent: "#B4A78F" },
    hoverArt: { pattern: "table", base: "#EAE3D6", accent: "#B4A78F" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "brass-taper-holders",
    name: "Brass Taper Candleholder, Set of 3",
    collection: "linens",
    price: 68,
    description: "Three heights of solid brass, aged to a soft satin finish. Tapers included.",
    tags: ["gift", "new"],
    art: { pattern: "brass", base: "#F3EDE2", accent: "#A8894F" },
    hoverArt: { pattern: "table", base: "#2E2723", accent: "#D6A85D" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "pasta-bowls-cream",
    name: "Wide Pasta Bowl in Cream, Set of 4",
    collection: "bowls",
    price: 98,
    description: "A low, wide bowl that works as hard for salads and grain bowls as it does for pasta.",
    tags: ["best"],
    art: { pattern: "rim", base: "#F6F1E8", accent: "#C9B79B" },
    hoverArt: { pattern: "table", base: "#F6F1E8", accent: "#C9B79B" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "cereal-bowls-blue",
    name: "Everyday Bowl in Denim Blue, Set of 4",
    collection: "bowls",
    price: 72,
    description: "The bowl you'll reach for every morning. Deep enough for soup, light enough for one hand.",
    tags: ["new"],
    art: { pattern: "dots", base: "#4E6A93", accent: "#F1E7D6" },
    hoverArt: { pattern: "shelf", base: "#F4EFE6", accent: "#4E6A93" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "host-gift-set",
    name: "The Host Gift Set: Board, Bowl & Napkins",
    collection: "serveware",
    price: 145,
    compareAt: 172,
    description: "Our olive wood board, a cream serving bowl and six linen napkins, boxed and wrapped. The gift every host actually wants.",
    badge: "Gift box",
    tags: ["gift"],
    art: { pattern: "shelf", base: "#F4EFE6", accent: "#7A4E2B" },
    hoverArt: { pattern: "wood", base: "#D9BE94", accent: "#7A4E2B" },
    image: "", hoverImage: "", buyUrl: "",
  },
  {
    id: "holiday-dessert-plates",
    name: "Holly Dessert Plate in White & Green, Set of 4",
    collection: "salad-plates",
    price: 76,
    description: "A crisp white plate with a hand-painted holly sprig. Just festive enough to use through New Year's.",
    badge: "Pre-order",
    tags: ["new", "gift"],
    art: { pattern: "leaf", base: "#FFFFFF", accent: "#3E6B45" },
    hoverArt: { pattern: "table", base: "#F1E9DD", accent: "#3E6B45" },
    image: "", hoverImage: "", buyUrl: "",
  },
];

// Editorial "trend" tiles under the hero
export const trends = {
  eyebrow: "New in",
  heading: "Fall Table Trends",
  blurb: "These looks define the table this season. Discover the pieces behind the year's most memorable gatherings.",
  tiles: [
    { label: "Earth & Spice", collection: "dinner-plates", art: { pattern: "table", base: "#E6CDB4", accent: "#B85F3A" }, image: "" },
    { label: "Soft Greens", collection: "salad-plates", art: { pattern: "scallop", base: "#DCE3D6", accent: "#728A6D" }, image: "" },
    { label: "Candlelight", collection: "linens", art: { pattern: "brass", base: "#2E2723", accent: "#D6A85D" }, image: "" },
    { label: "Everyday Blue", collection: "bowls", art: { pattern: "dots", base: "#4E6A93", accent: "#F1E7D6" }, image: "" },
  ],
};

// Occasion tiles
export const occasions = [
  { label: "Thanksgiving", art: { pattern: "table", base: "#EAD9C4", accent: "#B85F3A" }, image: "" },
  { label: "Holiday Formal", art: { pattern: "brass", base: "#2E2723", accent: "#D6A85D" }, image: "" },
  { label: "Sunday Brunch", art: { pattern: "scallop", base: "#E3E7DD", accent: "#728A6D" }, image: "" },
  { label: "Housewarming", art: { pattern: "shelf", base: "#F4EFE6", accent: "#7A4E2B" }, image: "" },
  { label: "Bridal Registry", art: { pattern: "rim", base: "#F6F1E8", accent: "#C9B79B" }, image: "" },
];

// "Shop the Look" feature
export const look = {
  eyebrow: "Styled by us",
  heading: "Our Go-To Fall Table",
  blurb: "Layered neutrals, a little brass and one hand-painted platter down the middle. Everything here is in the showroom right now.",
  image: "",
  art: { pattern: "table", base: "#EAD9C4", accent: "#B85F3A" },
  productIds: ["harvest-dinner-plate", "sage-scallop-salad", "botanical-oval-platter", "brass-taper-holders"],
};

export const gallery = [
  { id: "g1", caption: "Thanksgiving table, Harvest plates with the Botanical platter", art: { pattern: "table", base: "#EAD9C4", accent: "#B85F3A" }, image: "" },
  { id: "g2", caption: "Sunday brunch on the Scalloped Sage plates", art: { pattern: "scallop", base: "#DCE3D6", accent: "#728A6D" }, image: "" },
  { id: "g3", caption: "Olive wood boards, fresh from the shipment", art: { pattern: "wood", base: "#D9BE94", accent: "#7A4E2B" }, image: "" },
  { id: "g4", caption: "Candlelit dinner for eight", art: { pattern: "brass", base: "#2E2723", accent: "#D6A85D" }, image: "" },
  { id: "g5", caption: "The showroom shelves this fall", art: { pattern: "shelf", base: "#F4EFE6", accent: "#728A6D" }, image: "" },
  { id: "g6", caption: "Coffee corner with the Slow Morning mugs", art: { pattern: "dots", base: "#33456B", accent: "#F1E7D6" }, image: "" },
  { id: "g7", caption: "A client's finished dining room", art: { pattern: "rim", base: "#F1E9DD", accent: "#B85F3A" }, image: "" },
  { id: "g8", caption: "Amber tumblers at golden hour", art: { pattern: "ribbed", base: "#E9CD97", accent: "#A8784A" }, image: "" },
];

// Put a YouTube ID in youtubeId (e.g. "dQw4w9WgXcQ") or an MP4 in src.
export const videos = [
  { id: "v1", title: "Inside the Showroom", blurb: "Five minutes inside the house, room by room.", youtubeId: "", src: "" },
  { id: "v2", title: "How to Layer a Place Setting", blurb: "Plates, linens and candles without overthinking it.", youtubeId: "", src: "" },
  { id: "v3", title: "Unboxing the Fall Arrivals", blurb: "What just came in and what's going fast.", youtubeId: "", src: "" },
];

export const about = {
  eyebrow: "Our story",
  heading: "From our kitchen table to yours",
  paragraphs: [
    "Tabletop Stop started the way a lot of good things do: with too many dishes. What began as a love of hunting down beautiful plates for family dinners turned into friends asking where they could buy them, and then friends of friends.",
    "Today our home doubles as the showroom. Every piece is chosen by hand, used at our own table first, and only makes the shelves if it's something we'd be proud to give as a gift. We're small on purpose, so we can know every piece and every customer.",
    "Whether you're setting your first apartment table or finally replacing the wedding china, we'd love to help you find something you'll reach for every day.",
  ],
  signature: "The Tabletop Stop family",
  image: "",
  art: { pattern: "shelf", base: "#F4EFE6", accent: "#7A4E2B" },
};

export const testimonials = [
  { quote: "I came for two mugs and left with a whole dinner set. It felt like shopping at a friend's house, if your friend had impeccable taste.", name: "Karen M.", detail: "Showroom visit" },
  { quote: "The platter arrived wrapped like a present, with a handwritten note. It's been on my table every Sunday since.", name: "Dana R.", detail: "Online order" },
  { quote: "She built a registry that actually matched how we live. Our guests loved that it all came from a small shop.", name: "Jess & Tom", detail: "Wedding registry" },
];

export const faqs = [
  { q: "Can I visit the showroom?", a: "Yes. The showroom is our home, so we ask that you book a time first. Visits are relaxed and one-on-one, and there is always coffee on." },
  { q: "Do you ship?", a: `${business.shipping.region}. ${business.shipping.flatRate}. Everything is double-boxed and hand-wrapped, and we cover any breakage in transit.` },
  { q: "How do I pay for an online order?", a: "Add pieces to your bag and send us the order request. We confirm availability and reply with a secure payment link the same day. Card, Venmo and Zelle are all fine." },
  { q: "Can I return something?", a: "Unused pieces can be returned or exchanged within 14 days. Bring them by the showroom or send us a note and we will arrange it." },
  { q: "Do you do gift wrapping or registries?", a: "Both. Gift wrapping is complimentary on every order, and we are happy to build a registry for weddings, housewarmings and showers." },
  { q: "Are the dishes dishwasher safe?", a: "Most are, and each product says so. Wood boards and brass pieces should be hand-washed and dried." },
];

export const footerLinks = {
  Shop: [
    { label: "New Arrivals", href: "#shop" },
    { label: "Best Sellers", href: "#shop" },
    { label: "Gift Sets", href: "#shop" },
    { label: "Shop by Category", href: "#categories" },
  ],
  Explore: [
    { label: "Gallery", href: "#gallery" },
    { label: "Videos", href: "#videos" },
    { label: "Our Story", href: "#about" },
    { label: "Visit the Showroom", href: "#showroom" },
  ],
  "Customer Care": [
    { label: "Shipping & Pickup", href: "#faq" },
    { label: "Returns & Exchanges", href: "#faq" },
    { label: "Registries & Gifting", href: "#faq" },
    { label: "Contact Us", href: "#contact" },
  ],
};
