/** One consistent, hand-drawn stroke icon set. No external dependency, no
 * emoji. 24x24 viewBox, 1.75 stroke, round caps/joins -- every icon shares
 * these so the set reads as one family. Purely decorative by default
 * (aria-hidden); pass a real accessible name via props on the *button* that
 * wraps the icon, not on the icon itself. */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;
const base = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.75, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const IconUpload = (p: IconProps) => <svg {...base} {...p}><path d="M12 15V4M12 4l-4 4M12 4l4 4" /><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" /></svg>;
export const IconFile = (p: IconProps) => <svg {...base} {...p}><path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /></svg>;
export const IconFileDocx = (p: IconProps) => <svg {...base} {...p}><path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8.5 13v5M8.5 13l1.4 5M11.3 13l-1.4 5M11.3 13v5M13.5 18l1-5h1l1 5" /></svg>;
export const IconFilePdf = (p: IconProps) => <svg {...base} {...p}><path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6" /><path d="M8 18v-5h1.3a1.5 1.5 0 0 1 0 3H8M12.5 13v5M15 13v5M15 15.5h2" /></svg>;
export const IconTrash = (p: IconProps) => <svg {...base} {...p}><path d="M4 7h16" /><path d="M9 7V4h6v3" /><path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" /><path d="M10 11v6M14 11v6" /></svg>;
export const IconEye = (p: IconProps) => <svg {...base} {...p}><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>;
export const IconEyeOff = (p: IconProps) => <svg {...base} {...p}><path d="M3 3l18 18" /><path d="M10.6 5.2A9.9 9.9 0 0 1 12 5c6.4 0 10 7 10 7a16.6 16.6 0 0 1-3.2 4.2M6.6 6.6C3.7 8.4 2 12 2 12s3.6 7 10 7a9.6 9.6 0 0 0 3.4-.6" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" /></svg>;
export const IconCheck = (p: IconProps) => <svg {...base} {...p}><path d="M4 12l6 6L20 6" /></svg>;
export const IconCheckCircle = (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M8.5 12.5l2.5 2.5 4.5-5" /></svg>;
export const IconAlertCircle = (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 8v5" /><path d="M12 16h.01" /></svg>;
export const IconInfo = (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="12" r="9" /><path d="M12 11v5" /><path d="M12 7.5h.01" /></svg>;
export const IconX = (p: IconProps) => <svg {...base} {...p}><path d="M5 5l14 14M19 5L5 19" /></svg>;
export const IconChevronRight = (p: IconProps) => <svg {...base} {...p}><path d="M9 5l7 7-7 7" /></svg>;
export const IconChevronDown = (p: IconProps) => <svg {...base} {...p}><path d="M5 9l7 7 7-7" /></svg>;
export const IconHome = (p: IconProps) => <svg {...base} {...p}><path d="M4 11l8-7 8 7" /><path d="M6 10v9a1 1 0 0 0 1 1h3v-6h4v6h3a1 1 0 0 0 1-1v-9" /></svg>;
export const IconHistory = (p: IconProps) => <svg {...base} {...p}><path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v4h4" /><path d="M12 7v5l3.5 2" /></svg>;
export const IconLogout = (p: IconProps) => <svg {...base} {...p}><path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" /></svg>;
export const IconUser = (p: IconProps) => <svg {...base} {...p}><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" /></svg>;
export const IconMenu = (p: IconProps) => <svg {...base} {...p}><path d="M4 7h16M4 12h16M4 17h16" /></svg>;
export const IconSearch = (p: IconProps) => <svg {...base} {...p}><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>;
export const IconDatabase = (p: IconProps) => <svg {...base} {...p}><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></svg>;
export const IconFlask = (p: IconProps) => <svg {...base} {...p}><path d="M9 2h6" /><path d="M10 2v6.5L4.5 19a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 8.5V2" /><path d="M7.5 15h9" /></svg>;
export const IconLoader = (p: IconProps) => <svg {...base} {...p}><path d="M12 3a9 9 0 1 0 9 9" /></svg>;
export const IconSparkle = (p: IconProps) => <svg {...base} {...p}><path d="M12 3l1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3Z" /></svg>;
export const IconPlus = (p: IconProps) => <svg {...base} {...p}><path d="M12 5v14M5 12h14" /></svg>;
export const IconCloud = (p: IconProps) => <svg {...base} {...p}><path d="M7 18h11a4 4 0 0 0 .5-7.97A6 6 0 0 0 7.1 11.1 4.5 4.5 0 0 0 7 18Z" /></svg>;
