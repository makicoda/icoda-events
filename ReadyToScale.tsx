/**
 * ReadyToScale — CTA section for the ICODA events page.
 *
 * Design tokens applied (from ICODA design system):
 *   Background ......... #0B0B1E  (site root bg, --color-bg-base)
 *   Card surface ....... #111128  (--color-bg-card)
 *   Primary accent ..... #5B50FF  (--color-accent-primary)
 *   Primary hover ...... #4A3FE6
 *   Secondary border ... rgba(255,255,255,0.10)  (--color-border-subtle)
 *   Text primary ....... #FFFFFF
 *   Text muted ......... rgba(255,255,255,0.55)
 *   Font family ........ 'Inter', sans-serif
 *   Border radius ...... 12px buttons / 16px card (--radius-card)
 *   Spacing unit ....... 4px base (Tailwind scale)
 */

import React from "react";

// Countries shown as flag badges (ISO-3166-1 alpha-2 → display name)
const COUNTRIES: { code: string; name: string; emoji: string }[] = [
  { code: "us", name: "USA",         emoji: "🇺🇸" },
  { code: "de", name: "Germany",     emoji: "🇩🇪" },
  { code: "ch", name: "Swiss",       emoji: "🇨🇭" },
  { code: "pl", name: "Poland",      emoji: "🇵🇱" },
  { code: "it", name: "Italy",       emoji: "🇮🇹" },
  { code: "tr", name: "Turkey",      emoji: "🇹🇷" },
  { code: "ve", name: "Venezuela",   emoji: "🇻🇪" },
  { code: "eg", name: "Egypt",       emoji: "🇪🇬" },
  { code: "pa", name: "Panama",      emoji: "🇵🇦" },
  { code: "th", name: "Thailand",    emoji: "🇹🇭" },
  { code: "id", name: "Indonesia",   emoji: "🇮🇩" },
  { code: "cn", name: "China",       emoji: "🇨🇳" },
  { code: "jp", name: "Japan",       emoji: "🇯🇵" },
  { code: "me", name: "Montenegro",  emoji: "🇲🇪" },
];

// Approximate [left%, top%] positions on the world-map SVG viewBox (0–100)
// Tuned for a standard equirectangular projection.
const PIN_POSITIONS: Record<string, [number, number]> = {
  us: [17, 38],
  ve: [27, 53],
  pa: [22, 52],
  de: [49, 28],
  ch: [49, 31],
  pl: [51, 27],
  it: [50, 34],
  tr: [56, 34],
  me: [51, 32],
  eg: [55, 42],
  th: [73, 48],
  id: [77, 56],
  cn: [75, 37],
  jp: [83, 33],
};

/* ─── Inline SVG world map (simplified outline, no fill) ─── */
// Uses a lightweight path set — the same "ghost map" style as on icoda.io.
const WorldMapSVG: React.FC<{ className?: string }> = ({ className }) => (
  <svg
    className={className}
    viewBox="0 0 1000 500"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    {/* Simplified continents as filled shapes with very low opacity */}
    <g fill="rgba(91,80,255,0.08)" stroke="rgba(91,80,255,0.18)" strokeWidth="1.2">
      {/* North America */}
      <path d="M60,60 L200,50 L220,80 L210,120 L180,160 L140,200 L100,220 L70,200 L50,160 L40,120 Z" />
      {/* South America */}
      <path d="M160,230 L220,220 L240,260 L230,320 L200,370 L170,360 L150,310 L140,270 Z" />
      {/* Europe */}
      <path d="M430,60 L530,55 L545,80 L530,110 L490,120 L460,110 L440,90 Z" />
      {/* Africa */}
      <path d="M450,150 L550,145 L565,200 L560,300 L530,360 L490,370 L460,340 L440,280 L435,210 Z" />
      {/* Asia */}
      <path d="M545,55 L820,50 L850,80 L840,160 L800,200 L740,210 L680,190 L620,200 L580,180 L555,140 L540,100 Z" />
      {/* Southeast Asia / Indonesia */}
      <path d="M720,230 L820,220 L840,250 L810,270 L770,265 L730,255 Z" />
      {/* Australia */}
      <path d="M760,290 L880,285 L900,330 L880,380 L830,400 L780,385 L755,340 Z" />
    </g>

    {/* Subtle latitude/longitude grid */}
    <g stroke="rgba(255,255,255,0.04)" strokeWidth="0.8" fill="none">
      {[100, 200, 300, 400].map((y) => (
        <line key={y} x1="0" y1={y} x2="1000" y2={y} />
      ))}
      {[100, 200, 300, 400, 500, 600, 700, 800, 900].map((x) => (
        <line key={x} x1={x} y1="0" x2={x} y2="500" />
      ))}
    </g>
  </svg>
);

/* ─── Component ─── */
export const ReadyToScale: React.FC = () => {
  return (
    <section
      style={{
        background: "#0B0B1E",
        fontFamily: "'Inter', sans-serif",
        position: "relative",
        overflow: "hidden",
        padding: "80px 60px",
      }}
    >
      {/* ── Map background ── */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        <WorldMapSVG
          className=""
          /* fill entire section width */
        />

        {/* Country pins overlaid on the map */}
        {COUNTRIES.map(({ code, name, emoji }) => {
          const pos = PIN_POSITIONS[code];
          if (!pos) return null;
          const [left, top] = pos;
          return (
            <div
              key={code}
              title={name}
              style={{
                position: "absolute",
                left: `${left}%`,
                top: `${top}%`,
                transform: "translate(-50%, -50%)",
                fontSize: "22px",
                lineHeight: 1,
                filter: "drop-shadow(0 2px 6px rgba(0,0,0,0.6))",
              }}
            >
              {emoji}
            </div>
          );
        })}
      </div>

      {/* ── Content card ── */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          maxWidth: "720px",
        }}
      >
        {/* Headline — uses ICODA gradient text treatment */}
        <h2
          style={{
            fontSize: "clamp(36px, 5vw, 56px)",
            fontWeight: 700,
            lineHeight: 1.15,
            letterSpacing: "-0.5px",
            margin: "0 0 32px",
            background: "linear-gradient(90deg, #ffffff 0%, rgba(255,255,255,0.65) 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          Ready to scale with&nbsp;AI?
        </h2>

        {/* Country badges row — matches the PHP foreach output */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "8px",
            marginBottom: "40px",
          }}
        >
          {COUNTRIES.map(({ code, name, emoji }) => (
            <div
              key={code}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 14px",
                borderRadius: "8px",
                background: "rgba(91,80,255,0.08)",
                border: "1px solid rgba(91,80,255,0.18)",
                fontSize: "13px",
                fontWeight: 500,
                color: "rgba(255,255,255,0.75)",
                backdropFilter: "blur(4px)",
                transition: "background 0.2s, border-color 0.2s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = "rgba(91,80,255,0.16)";
                (e.currentTarget as HTMLElement).style.borderColor = "rgba(91,80,255,0.35)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = "rgba(91,80,255,0.08)";
                (e.currentTarget as HTMLElement).style.borderColor = "rgba(91,80,255,0.18)";
              }}
            >
              <span style={{ fontSize: "16px", lineHeight: 1 }}>{emoji}</span>
              <span>{name}</span>
            </div>
          ))}
        </div>

        {/* CTA buttons — primary (#5B50FF) + secondary (ghost) */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "12px",
            alignItems: "center",
          }}
        >
          {/* Primary — "Book Strategy Call" */}
          <a
            href="https://calendly.com/as-stive/30min"
            style={{
              display: "inline-block",
              padding: "14px 32px",
              borderRadius: "12px",
              background: "#5B50FF",
              color: "#ffffff",
              fontSize: "15px",
              fontWeight: 600,
              textDecoration: "none",
              letterSpacing: "0.2px",
              transition: "background 0.2s, transform 0.15s",
              whiteSpace: "nowrap",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "#4A3FE6";
              (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "#5B50FF";
              (e.currentTarget as HTMLElement).style.transform = "none";
            }}
          >
            Book Strategy Call
          </a>

          {/* Secondary — "Get Proposal" (ghost style) */}
          <a
            href="#get-proposal"
            style={{
              display: "inline-block",
              padding: "14px 32px",
              borderRadius: "12px",
              background: "rgba(255,255,255,0.06)",
              border: "1px solid rgba(255,255,255,0.12)",
              color: "rgba(255,255,255,0.75)",
              fontSize: "15px",
              fontWeight: 600,
              textDecoration: "none",
              letterSpacing: "0.2px",
              transition: "background 0.2s, border-color 0.2s, color 0.2s",
              whiteSpace: "nowrap",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLElement;
              el.style.background = "rgba(255,255,255,0.1)";
              el.style.borderColor = "rgba(255,255,255,0.25)";
              el.style.color = "#ffffff";
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLElement;
              el.style.background = "rgba(255,255,255,0.06)";
              el.style.borderColor = "rgba(255,255,255,0.12)";
              el.style.color = "rgba(255,255,255,0.75)";
            }}
          >
            Get Proposal
          </a>
        </div>
      </div>

      {/* ── Responsive styles (injected once) ── */}
      <style>{`
        @media (max-width: 640px) {
          .rts-section { padding: 56px 24px !important; }
          .rts-headline { font-size: 32px !important; }
          .rts-actions { flex-direction: column; align-items: stretch !important; }
          .rts-actions a { text-align: center; }
        }
      `}</style>
    </section>
  );
};

export default ReadyToScale;
