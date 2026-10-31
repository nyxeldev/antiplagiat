"use client";
import { useId, useState, type ReactNode } from "react";
import { IconUpload } from "../icons";
import styles from "./ui.module.css";

export function Dropzone({
  label, hint, accept, multiple, onFiles, onLight, describedBy,
}: { label: string; hint: string; accept: string; multiple?: boolean; onFiles: (files: File[]) => void; onLight?: boolean; describedBy?: string }) {
  const [dragging, setDragging] = useState(false);
  const id = useId();
  return (
    <div
      className={`${styles.dropzone} ${dragging ? styles.dragging : ""} ${onLight ? styles.onLight : ""}`}
      onDragOver={event => { event.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={event => {
        event.preventDefault(); setDragging(false);
        const files = Array.from(event.dataTransfer.files);
        if (files.length) onFiles(files);
      }}
    >
      <div className={styles.dropzoneIcon} aria-hidden="true"><IconUpload /></div>
      <label htmlFor={id} className={styles.dropzoneTitle}>{label}</label>
      <p className={styles.dropzoneHint}>{hint}</p>
      <input id={id} type="file" accept={accept} multiple={multiple} aria-describedby={describedBy}
        onChange={event => {
          const files = Array.from(event.target.files ?? []); event.target.value = "";
          if (files.length) onFiles(files);
        }} />
    </div>
  );
}

export function StepBadge({ step, children, onLight }: { step: number; children: ReactNode; onLight?: boolean }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--sp-3)", marginBottom: "var(--sp-3)" }}>
      <span style={{
        display: "grid", placeItems: "center", width: "1.75rem", height: "1.75rem", borderRadius: "999px",
        background: "var(--accent-soft-on-dark)", color: "var(--accent)", fontWeight: 700, fontSize: "var(--fs-sm)", flex: "none",
      }}>{step}</span>
      <h3 style={{ fontSize: "var(--fs-base)", color: onLight ? "var(--ink-on-light)" : "var(--ink-on-dark)" }}>{children}</h3>
    </div>
  );
}
