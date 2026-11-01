"use client";
import { motion } from "framer-motion";
import { useId, type ReactNode } from "react";
import styles from "./ui.module.css";

export function Tabs({
  items, active, onChange, onLight,
}: { items: { id: string; label: ReactNode }[]; active: string; onChange: (id: string) => void; onLight?: boolean }) {
  const name = useId();
  return (
    <div role="tablist" aria-label="Qarash" className={`${styles.tablist} ${onLight ? styles.onLight : ""}`}>
      {items.map(item => (
        <button key={item.id} type="button" role="tab" id={`${name}-${item.id}`} aria-selected={active === item.id}
          aria-controls={`${name}-panel-${item.id}`} className={styles.tab} onClick={() => onChange(item.id)}>
          {item.label}
          {active === item.id && <motion.span layoutId={`${name}-indicator`} className={styles.tabIndicator} style={{ left: 0, right: 0 }} transition={{ duration: 0.22 }} />}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ id, active, children }: { id: string; active: string; children: ReactNode }) {
  if (id !== active) return null;
  return <div role="tabpanel" id={`panel-${id}`}>{children}</div>;
}
