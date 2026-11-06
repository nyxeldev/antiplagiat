"use client";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { EASE_OUT } from "../motion";
import { Button } from "./primitives";
import styles from "./ui.module.css";

const FOCUSABLE = 'a[href],button:not([disabled]),textarea,input,select,[tabindex]:not([tabindex="-1"])';

/** Accessible modal: traps focus, closes on Escape, restores focus to the
 * trigger on close, blocks interaction with the page behind it. Rendered
 * through a portal so it always sits above everything else. */
export function Dialog({ open, onClose, title, children, onLight, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; onLight?: boolean; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<Element | null>(null);

  useEffect(() => {
    if (!open) return;
    trigger.current = document.activeElement;
    const node = ref.current;
    const focusables = () => Array.from(node?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
    focusables()[0]?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") { onClose(); return; }
      if (event.key !== "Tab") return;
      const items = focusables(); if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      (trigger.current as HTMLElement | null)?.focus?.();
    };
  }, [open, onClose]);

  if (typeof document === "undefined") return null;
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className={styles.dialogBackdrop} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }} onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
          <motion.div ref={ref} role="dialog" aria-modal="true" aria-labelledby="dialog-title"
            className={`${styles.dialog} ${wide ? styles.dialogWide : ""} ${onLight ? styles.onLight : ""}`}
            initial={{ opacity: 0, scale: 0.96, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.22, ease: EASE_OUT }}>
            <h2 id="dialog-title">{title}</h2>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export function ConfirmDialog({
  open, onClose, onConfirm, title, description, confirmLabel = "Tasdiqlash", busy, onLight,
}: { open: boolean; onClose: () => void; onConfirm: () => void; title: string; description: ReactNode; confirmLabel?: string; busy?: boolean; onLight?: boolean }) {
  return (
    <Dialog open={open} onClose={onClose} title={title} onLight={onLight}>
      <p>{description}</p>
      <div className={styles.dialogActions}>
        <Button variant="secondary" onLight={onLight} onClick={onClose} disabled={busy}>Bekor qilish</Button>
        <Button variant="destructive" onLight={onLight} onClick={onConfirm} loading={busy}>{confirmLabel}</Button>
      </div>
    </Dialog>
  );
}
