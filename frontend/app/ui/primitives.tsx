"use client";
import { motion } from "framer-motion";
import { forwardRef, useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { tap } from "../motion";
import { IconAlertCircle, IconCheckCircle, IconChevronDown, IconEye, IconEyeOff, IconInfo, IconLoader } from "../icons";
import styles from "./ui.module.css";

function cx(...parts: Array<string | false | undefined>) { return parts.filter(Boolean).join(" "); }

/* Framer Motion's own onDrag/onAnimationStart/... signatures conflict with
 * the native DOM ones; every component below spreads native button/input
 * attributes onto a motion.* element, so the native versions of these
 * specific handlers are dropped from the prop type (nothing here ever sets
 * them anyway). */
type NonMotionButtonAttrs = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart" | "onAnimationEnd" | "onAnimationIteration">;

/* ---------------------------- Button --------------------------------- */
type ButtonVariant = "primary" | "secondary" | "destructive" | "ghost";
export interface ButtonProps extends NonMotionButtonAttrs {
  variant?: ButtonVariant; loading?: boolean; icon?: ReactNode; onLight?: boolean;
}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", loading, icon, onLight, className, children, disabled, ...rest }, ref,
) {
  return (
    <motion.button ref={ref} whileTap={!disabled && !loading ? tap : undefined}
      className={cx(styles.btn, styles[`btn-${variant}`], onLight && styles.onLight, className)}
      disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <IconLoader className={styles.spin} /> : icon}
      {children && <span>{children}</span>}
    </motion.button>
  );
});

export interface IconButtonProps extends NonMotionButtonAttrs {
  label: string; icon: ReactNode; variant?: ButtonVariant; onLight?: boolean;
}
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, variant = "ghost", onLight, className, ...rest }, ref,
) {
  return (
    <motion.button ref={ref} whileTap={tap} aria-label={label}
      className={cx(styles.iconBtn, styles[`btn-${variant}`], onLight && styles.onLight, className)} {...rest}>
      {icon}
    </motion.button>
  );
});

/* ---------------------------- Field / Input --------------------------------- */
export interface FieldProps { label: string; hint?: string; error?: string; onLight?: boolean; children: ReactNode; htmlFor?: string; }
export function Field({ label, hint, error, onLight, children, htmlFor }: FieldProps) {
  return (
    <div className={cx(styles.field, onLight && styles.onLight)}>
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && !error && <span style={{ fontSize: "var(--fs-xs)", color: "var(--ink-on-dark-faint)" }}>{hint}</span>}
      {error && <Alert variant="error" compact onLight={onLight}>{error}</Alert>}
    </div>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> { onLight?: boolean; invalid?: boolean; }
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ onLight, invalid, className, ...rest }, ref) {
  return <input ref={ref} className={cx(styles.input, onLight && styles.onLight, className)} aria-invalid={invalid || undefined} {...rest} />;
});

export const PasswordInput = forwardRef<HTMLInputElement, InputProps>(function PasswordInput({ onLight, invalid, className, ...rest }, ref) {
  const [visible, setVisible] = useState(false);
  const uid = useId();
  return (
    <div className={cx(styles.inputWrap, onLight && styles.onLight)}>
      <input ref={ref} id={rest.id ?? uid} type={visible ? "text" : "password"}
        className={cx(styles.input, onLight && styles.onLight, className)} aria-invalid={invalid || undefined}
        style={{ paddingRight: "2.5rem" }} {...rest} />
      <button type="button" className={styles.inputToggle} onClick={() => setVisible(v => !v)}
        aria-label={visible ? "Parolni yashirish" : "Parolni ko‘rsatish"} aria-pressed={visible} tabIndex={-1}>
        {visible ? <IconEyeOff /> : <IconEye />}
      </button>
    </div>
  );
});

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> { onLight?: boolean; }
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select({ onLight, className, children, ...rest }, ref) {
  return (
    <div className={cx(styles.selectWrap, onLight && styles.onLight)}>
      <select ref={ref} className={cx(styles.input, styles.select, onLight && styles.onLight, className)} {...rest}>{children}</select>
      <IconChevronDown className={styles.selectChevron} />
    </div>
  );
});

/* ---------------------------- Alert --------------------------------- */
type AlertVariant = "info" | "success" | "error" | "warning";
const ALERT_ICON: Record<AlertVariant, ReactNode> = {
  info: <IconInfo />, success: <IconCheckCircle />, error: <IconAlertCircle />, warning: <IconAlertCircle />,
};
export function Alert({ variant = "info", onLight, compact, children }: { variant?: AlertVariant; onLight?: boolean; compact?: boolean; children: ReactNode }) {
  return (
    <div role={variant === "error" ? "alert" : "status"}
      className={cx(styles.alert, styles[`alert-${variant}`], onLight && styles.onLight)}
      style={compact ? { padding: "0.5rem 0.75rem" } : undefined}>
      {ALERT_ICON[variant]}
      <div>{children}</div>
    </div>
  );
}

/* ---------------------------- Card --------------------------------- */
export function Card({ onLight, pad = true, className, children, ...rest }: { onLight?: boolean; pad?: boolean; className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx(styles.card, pad && styles.cardPad, onLight && styles.onLight, className)} {...rest}>{children}</div>;
}

/* ---------------------------- Badge --------------------------------- */
type BadgeVariant = "neutral" | "accent" | "cyan" | "danger";
export function Badge({ variant = "neutral", onLight, icon, children }: { variant?: BadgeVariant; onLight?: boolean; icon?: ReactNode; children: ReactNode }) {
  return <span className={cx(styles.badge, styles[`badge-${variant}`], onLight && styles.onLight)}>{icon}{children}</span>;
}

/* ---------------------------- EmptyState --------------------------------- */
export function EmptyState({ icon, title, description, action, onLight }: { icon: ReactNode; title: string; description?: string; action?: ReactNode; onLight?: boolean }) {
  return (
    <div className={cx(styles.empty, onLight && styles.onLight)}>
      <div className={styles.emptyIcon}>{icon}</div>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

/* ---------------------------- Skeleton --------------------------------- */
export function Skeleton({ width, height = "1rem", onLight, style }: { width?: string | number; height?: string | number; onLight?: boolean; style?: React.CSSProperties }) {
  return <div className={cx(styles.skeleton, onLight && styles.onLight)} style={{ width, height, ...style }} aria-hidden="true" />;
}

/* ---------------------------- Pagination --------------------------------- */
export function Pagination({ page, hasNext, onChange, disabled, onLight }: { page: number; hasNext: boolean; onChange: (page: number) => void; disabled?: boolean; onLight?: boolean }) {
  return (
    <nav className={cx(styles.pagination, onLight && styles.onLight)} aria-label="Sahifalash">
      <Button variant="secondary" onLight={onLight} disabled={page <= 1 || disabled} onClick={() => onChange(page - 1)}>Oldingi</Button>
      <span>{page}-sahifa</span>
      <Button variant="secondary" onLight={onLight} disabled={!hasNext || disabled} onClick={() => onChange(page + 1)}>Keyingi</Button>
    </nav>
  );
}
