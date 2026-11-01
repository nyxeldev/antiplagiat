/** Abstract illustration of the product's actual function -- two documents
 * with a few corresponding lines connected -- never a literal screenshot of
 * real results, so it cannot be mistaken for an actual check. Purely
 * decorative (aria-hidden). */
export default function CompareIllustration(props: React.SVGProps<SVGSVGElement>) {
  const pageLines = (x: number, matched: number[]) =>
    Array.from({ length: 7 }, (_, i) => (
      <rect key={i} x={x} y={28 + i * 14} width={i === 6 ? 70 : 118} height={6} rx={3}
        fill={matched.includes(i) ? "var(--accent)" : "currentColor"} opacity={matched.includes(i) ? 0.9 : 0.22} />
    ));
  return (
    <svg viewBox="0 0 360 280" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
      <g opacity="0.08" stroke="currentColor" strokeWidth="1">
        <circle cx="180" cy="140" r="120" />
        <circle cx="180" cy="140" r="86" />
      </g>
      <g transform="translate(26,18)">
        <rect x="0" y="0" width="150" height="196" rx="14" fill="var(--bg-2)" stroke="var(--line-dark-strong)" />
        {pageLines(16, [2, 4])}
      </g>
      <g transform="translate(184,46)">
        <rect x="0" y="0" width="150" height="196" rx="14" fill="var(--bg-3)" stroke="var(--line-dark-strong)" />
        {pageLines(16, [1, 3])}
      </g>
      <g stroke="var(--accent)" strokeWidth="1.5" strokeDasharray="3 4" opacity="0.8">
        <path d="M144 74 L214 123" />
        <path d="M144 102 L214 151" />
      </g>
      <circle cx="144" cy="74" r="4" fill="var(--accent)" />
      <circle cx="214" cy="123" r="4" fill="var(--accent)" />
      <circle cx="144" cy="102" r="4" fill="var(--accent)" />
      <circle cx="214" cy="151" r="4" fill="var(--accent)" />
    </svg>
  );
}
