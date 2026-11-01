"use client";
import { motion, useReducedMotion } from "framer-motion";
import { CountUp } from "../motion";

/** The report's headline number: a segmented radial ring plus a large
 * figure. Decorative ring only -- the percentage text itself is always in
 * the DOM as real text, so a screen reader gets the final value regardless
 * of the ring or the count-up animation. Ring never implies a verdict:
 * color is a single fixed accent hue, never switched by thresholds. */
export function Metric({
  value, label, detail, size = 128, onLight,
}: { value: number; label: string; detail?: string; size?: number; onLight?: boolean }) {
  const reduced = useReducedMotion();
  const radius = (size - 14) / 2;
  const circumference = 2 * Math.PI * radius;
  const fraction = Math.min(1, Math.max(0, value / 100));
  const track = onLight ? "var(--line-light-strong)" : "var(--line-dark-strong)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-6)", flexWrap: "wrap" }}>
      <div style={{ position: "relative", width: size, height: size, flex: "none" }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={track} strokeWidth="10" />
          <motion.circle
            cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--accent)" strokeWidth="10" strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - fraction) }}
            transition={reduced ? { duration: 0 } : { duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          />
        </svg>
        <div style={{
          position: "absolute", inset: 0, display: "grid", placeItems: "center",
          fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "clamp(1.3rem, 3vw, 1.7rem)",
          color: onLight ? "var(--ink-on-light)" : "var(--ink-on-dark)", fontVariantNumeric: "tabular-nums",
        }}>
          <CountUp value={value} format={v => `${v.toLocaleString("uz-UZ", { maximumFractionDigits: 1 })}%`} />
        </div>
      </div>
      <div style={{ minWidth: "12rem" }}>
        <h3 style={{ fontSize: "var(--fs-md)", marginBottom: "0.35rem" }}>{label}</h3>
        {detail && <p style={{ color: onLight ? "var(--ink-on-light-muted)" : "var(--ink-on-dark-muted)", fontSize: "var(--fs-sm)", lineHeight: 1.55 }}>{detail}</p>}
      </div>
    </div>
  );
}
