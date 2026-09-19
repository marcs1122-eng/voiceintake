// Hand-drawn style SVG placeholders. Each product / gallery item picks a
// pattern and two colors; once a real photo is added the art is no longer shown.

function Plate({ base, accent, children, shadow = true }) {
  return (
    <>
      {shadow && <ellipse cx="50" cy="56" rx="38" ry="34" fill="rgba(0,0,0,0.12)" />}
      <circle cx="50" cy="50" r="38" fill={base} />
      <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth="1" />
      {children}
      <circle cx="50" cy="50" r="26" fill="none" stroke="rgba(0,0,0,0.07)" strokeWidth="0.8" />
      <path d="M22 38 Q30 22 46 18" fill="none" stroke="rgba(255,255,255,0.55)" strokeWidth="2.5" strokeLinecap="round" />
    </>
  );
}

function Rim({ base, accent }) {
  return (
    <Plate base={base} accent={accent}>
      <circle cx="50" cy="50" r="35" fill="none" stroke={accent} strokeWidth="3.2" />
      <circle cx="50" cy="50" r="31" fill="none" stroke={accent} strokeWidth="0.8" opacity="0.6" />
      {Array.from({ length: 40 }).map((_, i) => (
        <circle key={i} cx={50 + Math.cos(i * 1.7) * (8 + (i * 7) % 16)} cy={50 + Math.sin(i * 1.7) * (8 + (i * 7) % 16)} r="0.55" fill={accent} opacity="0.35" />
      ))}
    </Plate>
  );
}

function Scallop({ base, accent }) {
  const pts = 18;
  let d = "";
  for (let i = 0; i < pts; i++) {
    const a1 = (i / pts) * Math.PI * 2;
    const a2 = ((i + 0.5) / pts) * Math.PI * 2;
    const a3 = ((i + 1) / pts) * Math.PI * 2;
    const x1 = 50 + Math.cos(a1) * 36, y1 = 50 + Math.sin(a1) * 36;
    const xc = 50 + Math.cos(a2) * 41, yc = 50 + Math.sin(a2) * 41;
    const x3 = 50 + Math.cos(a3) * 36, y3 = 50 + Math.sin(a3) * 36;
    d += (i === 0 ? `M${x1} ${y1}` : "") + ` Q${xc} ${yc} ${x3} ${y3}`;
  }
  return (
    <>
      <path d={d + " Z"} transform="translate(0,6)" fill="rgba(0,0,0,0.12)" />
      <path d={d + " Z"} fill={base} stroke="rgba(0,0,0,0.08)" strokeWidth="0.8" />
      <circle cx="50" cy="50" r="27" fill="none" stroke={accent} strokeWidth="1.2" opacity="0.7" />
      <circle cx="50" cy="50" r="23" fill={accent} opacity="0.12" />
      <path d="M24 40 Q32 24 47 20" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth="2.5" strokeLinecap="round" />
    </>
  );
}

function Leaf({ base, accent }) {
  const leaf = (x, y, r, s = 1) => (
    <g transform={`translate(${x} ${y}) rotate(${r}) scale(${s})`} key={`${x}${y}`}>
      <path d="M0 0 C6 -8 14 -8 18 0 C14 8 6 8 0 0 Z" fill={accent} opacity="0.85" />
      <path d="M0 0 L18 0" stroke={base} strokeWidth="0.7" />
    </g>
  );
  return (
    <Plate base={base} accent={accent}>
      <path d="M22 62 C34 40 60 30 78 42" fill="none" stroke={accent} strokeWidth="1.1" />
      {leaf(28, 58, -40, 0.55)}
      {leaf(38, 48, -25, 0.6)}
      {leaf(50, 41, -10, 0.65)}
      {leaf(62, 38, 10, 0.6)}
      {leaf(34, 62, 30, 0.45)}
      {leaf(48, 52, 40, 0.5)}
      {leaf(66, 48, 60, 0.5)}
    </Plate>
  );
}

function Dots({ base, accent }) {
  return (
    <>
      <ellipse cx="52" cy="60" rx="30" ry="30" fill="rgba(0,0,0,0.14)" />
      {/* mug body */}
      <path d="M26 30 h44 a4 4 0 0 1 4 4 v36 a10 10 0 0 1 -10 10 h-32 a10 10 0 0 1 -10 -10 v-36 a4 4 0 0 1 4 -4 z" fill={base} />
      <path d="M74 40 h6 a10 10 0 0 1 0 20 h-6" fill="none" stroke={base} strokeWidth="6" strokeLinecap="round" />
      <path d="M74 40 h6 a10 10 0 0 1 0 20 h-6" fill="none" stroke="rgba(0,0,0,0.15)" strokeWidth="1" />
      <ellipse cx="48" cy="31" rx="26" ry="4.5" fill={accent} opacity="0.9" />
      <ellipse cx="48" cy="31" rx="21" ry="3" fill={base} opacity="0.8" />
      {[[36, 46], [50, 42], [62, 50], [40, 62], [56, 66], [30, 72], [66, 70]].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2.4" fill={accent} opacity="0.8" />
      ))}
      <path d="M29 36 v30" stroke="rgba(255,255,255,0.35)" strokeWidth="2.5" strokeLinecap="round" />
    </>
  );
}

function Ribbed({ base, accent }) {
  return (
    <>
      <ellipse cx="50" cy="84" rx="22" ry="5" fill="rgba(0,0,0,0.14)" />
      <path d="M32 22 h36 l-4 60 a4 4 0 0 1 -4 4 h-20 a4 4 0 0 1 -4 -4 z" fill={base} opacity="0.95" />
      {Array.from({ length: 7 }).map((_, i) => (
        <path key={i} d={`M${35 + i * 5} 26 L${36.5 + i * 4.3} 82`} stroke={accent} strokeWidth="1.3" opacity="0.45" />
      ))}
      <ellipse cx="50" cy="22" rx="18" ry="4" fill={accent} opacity="0.35" />
      <ellipse cx="50" cy="22" rx="18" ry="4" fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="1" />
      <path d="M37 30 v45" stroke="rgba(255,255,255,0.5)" strokeWidth="2.5" strokeLinecap="round" />
    </>
  );
}

function Wood({ base, accent }) {
  return (
    <>
      <path d="M20 40 C24 26 44 22 62 26 C78 30 84 44 80 58 C76 74 54 80 36 74 C22 70 16 54 20 40 Z" transform="translate(2,5)" fill="rgba(0,0,0,0.14)" />
      <path d="M20 40 C24 26 44 22 62 26 C78 30 84 44 80 58 C76 74 54 80 36 74 C22 70 16 54 20 40 Z" fill={base} />
      {[0, 1, 2, 3, 4].map((i) => (
        <path key={i} d={`M${24 + i * 2} ${40 + i * 5} C${34 + i * 3} ${30 + i * 5} ${56 + i} ${28 + i * 6} ${74 - i * 2} ${44 + i * 5}`} fill="none" stroke={accent} strokeWidth="0.8" opacity="0.55" />
      ))}
      <circle cx="26" cy="36" r="2.2" fill="none" stroke={accent} strokeWidth="0.8" />
      <circle cx="26" cy="36" r="0.8" fill={accent} />
    </>
  );
}

function Linen({ base, accent }) {
  return (
    <>
      <rect x="20" y="30" width="60" height="44" rx="2" transform="rotate(-6 50 52) translate(2,5)" fill="rgba(0,0,0,0.12)" />
      <rect x="20" y="30" width="60" height="44" rx="2" transform="rotate(-6 50 52)" fill={base} />
      <rect x="24" y="26" width="60" height="44" rx="2" transform="rotate(4 54 48)" fill={base} stroke="rgba(0,0,0,0.06)" />
      <g transform="rotate(4 54 48)" opacity="0.5">
        {Array.from({ length: 10 }).map((_, i) => (
          <line key={i} x1={24} y1={30 + i * 4.2} x2={84} y2={30 + i * 4.2} stroke={accent} strokeWidth="0.4" />
        ))}
        {Array.from({ length: 14 }).map((_, i) => (
          <line key={`v${i}`} x1={26 + i * 4.2} y1={26} x2={26 + i * 4.2} y2={70} stroke={accent} strokeWidth="0.4" />
        ))}
      </g>
      <rect x="24" y="26" width="60" height="44" rx="2" transform="rotate(4 54 48)" fill="none" stroke={accent} strokeWidth="1.2" strokeDasharray="1.5 1.5" opacity="0.7" />
    </>
  );
}

function Brass({ base, accent }) {
  const holder = (x, h, key) => (
    <g key={key}>
      <ellipse cx={x} cy="86" rx="9" ry="2.5" fill="rgba(0,0,0,0.15)" />
      <path d={`M${x - 7} 84 h14 l-4 -6 h-6 z`} fill={accent} />
      <rect x={x - 2.2} y={84 - h} width="4.4" height={h - 6} fill={accent} />
      <rect x={x - 5} y={84 - h - 3} width="10" height="4" rx="1" fill={accent} />
      <rect x={x - 2} y={84 - h - 26} width="4" height="24" rx="1" fill="#F6EFE3" stroke="rgba(0,0,0,0.06)" />
      <path d={`M${x} ${84 - h - 30} c-2 3 -2 5 0 7 c2 -2 2 -4 0 -7 z`} fill="#E8A33A" />
      <circle cx={x} cy={84 - h - 26} r="2.4" fill="#F6C766" opacity="0.7" />
    </g>
  );
  return (
    <>
      <rect x="0" y="0" width="100" height="100" fill={base} opacity="0" />
      {holder(30, 22, "a")}
      {holder(50, 34, "b")}
      {holder(70, 27, "c")}
    </>
  );
}

function Table({ base, accent }) {
  return (
    <>
      <rect x="0" y="52" width="100" height="48" fill={accent} opacity="0.18" />
      <path d="M0 52 h100 v4 h-100 z" fill={accent} opacity="0.3" />
      {[18, 50, 82].map((x, i) => (
        <g key={i}>
          <ellipse cx={x} cy="66" rx="14" ry="6" fill="rgba(0,0,0,0.12)" />
          <ellipse cx={x} cy="63" rx="14" ry="6" fill={base} />
          <ellipse cx={x} cy="63" rx="13" ry="5.2" fill="none" stroke={accent} strokeWidth="1" />
          <ellipse cx={x} cy="63" rx="8.5" ry="3.2" fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth="0.6" />
        </g>
      ))}
      <rect x="47" y="30" width="6" height="22" fill="#F6EFE3" />
      <path d="M50 24 c-2 3 -2 5 0 7 c2 -2 2 -4 0 -7z" fill="#E8A33A" />
      <path d="M30 78 h40" stroke={accent} strokeWidth="1" opacity="0.3" />
    </>
  );
}

function Shelf({ base, accent }) {
  const stack = (x, y, c, n) => Array.from({ length: n }).map((_, i) => (
    <g key={`${x}${y}${i}`}>
      <rect x={x - 9} y={y - i * 3} width="18" height="3" rx="1.5" fill={c} stroke="rgba(0,0,0,0.08)" strokeWidth="0.5" />
    </g>
  ));
  return (
    <>
      <rect x="10" y="36" width="80" height="2.5" fill={accent} opacity="0.5" />
      <rect x="10" y="66" width="80" height="2.5" fill={accent} opacity="0.5" />
      {stack(24, 33, "#EFE3D2", 4)}
      {stack(50, 33, "#D9E2D3", 3)}
      {stack(76, 33, "#33456B", 5)}
      {stack(24, 63, "#E8C384", 3)}
      <path d="M44 63 h14 a2 2 0 0 1 2 2 v-16 h-18 v16 a2 2 0 0 1 2 -2z" fill="#F4EEE2" stroke="rgba(0,0,0,0.08)" strokeWidth="0.5" />
      <circle cx="51" cy="54" r="3" fill={accent} opacity="0.5" />
      {stack(76, 63, "#E9E1D3", 2)}
      <ellipse cx="76" cy="55" rx="6" ry="1.5" fill="#B8935A" />
    </>
  );
}

const PATTERNS = { rim: Rim, scallop: Scallop, leaf: Leaf, dots: Dots, ribbed: Ribbed, wood: Wood, linen: Linen, brass: Brass, table: Table, shelf: Shelf };

export default function DishArt({ art, className = "", title }) {
  const { pattern = "rim", base = "#EFE3D2", accent = "#C4643B" } = art || {};
  const Pattern = PATTERNS[pattern] || Rim;
  // Background is a soft tint of the accent so every card feels like a styled photo
  const bg = `linear-gradient(165deg, ${mix(accent, "#F7F4EE", 0.9)}, ${mix(accent, "#ECE7DE", 0.82)})`;
  return (
    <div className={`tt-art ${className}`} style={{ background: bg }} role="img" aria-label={title || "Product illustration"}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
        <Pattern base={base} accent={accent} />
      </svg>
    </div>
  );
}

function mix(hexA, hexB, t) {
  const a = hexA.replace("#", ""), b = hexB.replace("#", "");
  const ch = (i) => Math.round(parseInt(a.slice(i, i + 2), 16) * (1 - t) + parseInt(b.slice(i, i + 2), 16) * t);
  return `rgb(${ch(0)}, ${ch(2)}, ${ch(4)})`;
}
