"use client";
import { IconFile, IconFileDocx, IconFilePdf, IconTrash } from "../icons";
import { IconButton } from "./primitives";
import styles from "./ui.module.css";
const MIB = 1024 * 1024;

function iconFor(name: string) {
  if (/\.docx$/i.test(name)) return <IconFileDocx />;
  if (/\.pdf$/i.test(name)) return <IconFilePdf />;
  return <IconFile />;
}

export function FileItem({ name, size, onRemove, removeLabel, error, onLight }: { name: string; size: number; onRemove: () => void; removeLabel: string; error?: boolean; onLight?: boolean }) {
  return (
    <div className={`${styles.fileItem} ${error ? styles.error : ""} ${onLight ? styles.onLight : ""}`}>
      <span className={styles.fileIcon}>{iconFor(name)}</span>
      <div className={styles.fileMeta}>
        <div className={styles.name}>{name}</div>
        <div className={styles.size}>{(size / MIB).toFixed(2)} MiB</div>
      </div>
      <IconButton label={removeLabel} icon={<IconTrash />} onLight={onLight} onClick={onRemove} />
    </div>
  );
}
