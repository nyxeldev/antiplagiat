/** A single subtle, monochrome 8-fold girih (Islamic geometric) motif, used as a
 * faint corner ornament on the hero card. Decorative only -- aria-hidden by the
 * caller. Pure stroke art, no fill, so it reads as a watermark rather than a logo. */
export default function GeometricMotif(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 200 200" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <g stroke="currentColor" strokeWidth="1.1">
        {Array.from({ length: 8 }, (_, i) => {
          const angle = (i * Math.PI) / 4;
          const x2 = 100 + 88 * Math.cos(angle);
          const y2 = 100 + 88 * Math.sin(angle);
          return <line key={i} x1="100" y1="100" x2={x2} y2={y2} />;
        })}
        {[88, 62, 36].map(r => (
          <polygon
            key={r}
            points={Array.from({ length: 8 }, (_, i) => {
              const angle = (i * Math.PI) / 4 - Math.PI / 8;
              return `${100 + r * Math.cos(angle)},${100 + r * Math.sin(angle)}`;
            }).join(" ")}
          />
        ))}
        <circle cx="100" cy="100" r="88" />
      </g>
    </svg>
  );
}
