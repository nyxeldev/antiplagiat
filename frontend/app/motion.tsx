"use client";
import { AnimatePresence, motion, useReducedMotion, type Variants } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";

/** Shared easing/timing so every transition in the app feels like one hand drew it. */
export const EASE = [0.16, 1, 0.3, 1] as const;
export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

const riseVariants: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0 },
};

/** Fades+rises content in once on mount; respects prefers-reduced-motion. */
export function Rise({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      variants={reduced ? undefined : riseVariants}
      initial={reduced ? undefined : "hidden"}
      animate={reduced ? undefined : "show"}
      transition={{ duration: 0.55, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/** Staggers its direct children in on mount (wrap each child in <StaggerItem>). */
export function Stagger({ children, className, stagger = 0.06 }: { children: ReactNode; className?: string; stagger?: number }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      initial={reduced ? undefined : "hidden"}
      animate={reduced ? undefined : "show"}
      variants={reduced ? undefined : { hidden: {}, show: { transition: { staggerChildren: stagger } } }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      className={className}
      variants={reduced ? undefined : riseVariants}
      transition={{ duration: 0.45, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

/** A number that counts up to its target once, then stays put. Pure cosmetic: the
 * real value is always in the DOM text immediately via the `format` fallback for
 * reduced-motion and non-JS cases is unnecessary here since this is client-only. */
export function CountUp({ value, format, duration = 0.9 }: { value: number; format: (n: number) => string; duration?: number }) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    if (reduced) {
      const id = requestAnimationFrame(() => setDisplay(value));
      return () => cancelAnimationFrame(id);
    }
    let raf = 0; const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / (duration * 1000));
      const eased = 1 - Math.pow(1 - t, 3);
      setDisplay(value * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return <>{format(display)}</>;
}

/** Crossfades between keyed children -- e.g. switching which source/match is shown. */
export function Crossfade({ id, children, className }: { id: string | number; children: ReactNode; className?: string }) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={id}
        className={className}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -6 }}
        transition={{ duration: 0.28, ease: EASE_OUT }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

/** Inline alert/notice that slides in and collapses out cleanly. */
export function Pop({ show, children, className }: { show: boolean; children: ReactNode; className?: string }) {
  return (
    <AnimatePresence initial={false}>
      {show && (
        <motion.div
          className={className}
          initial={{ opacity: 0, height: 0, marginTop: 0 }}
          animate={{ opacity: 1, height: "auto", marginTop: 12 }}
          exit={{ opacity: 0, height: 0, marginTop: 0 }}
          transition={{ duration: 0.3, ease: EASE_OUT }}
          style={{ overflow: "hidden" }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export const tap = { scale: 0.97 };
export const hoverLift = { y: -2 };

/** A fully custom, animated replacement for <details>/<summary>: same semantics
 * (a labelled toggle that reveals content), smooth height animation either way. */
export function Disclosure({
  summary, children, defaultOpen = false, className, summaryClassName,
}: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean; className?: string; summaryClassName?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  const reduced = useReducedMotion();
  return (
    <div className={className}>
      <button type="button" className={summaryClassName} aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <motion.span
          aria-hidden="true"
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.2, ease: EASE_OUT }}
          style={{ display: "inline-block", marginRight: "0.5em" }}
        >
          ▸
        </motion.span>
        {summary}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={reduced ? undefined : { height: 0, opacity: 0 }}
            animate={reduced ? undefined : { height: "auto", opacity: 1 }}
            exit={reduced ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: EASE_OUT }}
            style={{ overflow: "hidden" }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
