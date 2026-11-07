import { useEffect, useId, useRef, useState, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";
import type { LampState } from "../lib/node";
import { lampText } from "../lib/node";
import { fmtDateTime, fmtRelative } from "../lib/format";
import { Icon, type IconName } from "./Icon";

/* ── Lamp ─────────────────────────────────────────────────────────── */

export function Lamp({ state, size, label, blink }: { state: LampState; size?: "s" | "l"; label?: string; blink?: boolean }) {
  return (
    <span
      className={`lamp${size ? ` lamp-${size}` : ""}`}
      data-state={state}
      data-blink={blink || undefined}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  );
}

export function StatusLabel({ state, text }: { state: LampState; text?: string }) {
  return (
    <span className="status-label">
      <Lamp state={state} size="s" />
      <span>{text ?? lampText(state)}</span>
    </span>
  );
}

/* ── Clock: one shared ticker for relative times ─────────────────── */

let now = Date.now();
const clockListeners = new Set<() => void>();
setInterval(() => {
  now = Date.now();
  for (const listener of clockListeners) listener();
}, 15_000);

export function useNow(): number {
  return useSyncExternalStore(
    (listener) => {
      clockListeners.add(listener);
      return () => clockListeners.delete(listener);
    },
    () => now,
  );
}

export function RelTime({ iso, prefix }: { iso: string | null | undefined; prefix?: string }) {
  const current = useNow();
  if (!iso) return <span>nie</span>;
  return (
    <time dateTime={iso} title={fmtDateTime(iso)}>
      {prefix ? `${prefix} ` : ""}
      {fmtRelative(iso, current)}
    </time>
  );
}

/* ── Meter ────────────────────────────────────────────────────────── */

export function Meter({ value, label, caution = 75, stop = 90 }: { value: number | null; label: string; caution?: number; stop?: number }) {
  const v = value ?? 0;
  const lvl = v >= stop ? "stop" : v >= caution ? "caution" : undefined;
  return (
    <span
      className="meter"
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(v)}
      data-level={lvl}
      style={{ "--value": v } as CSSProperties}
    />
  );
}

/* ── States ───────────────────────────────────────────────────────── */

export function Loading({ label = "Lädt …" }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <div className="loading-line" />
      <span className="visually-hidden">{label}</span>
    </div>
  );
}

export function Empty({ title, children, icon = "info", action }: { title: string; children?: ReactNode; icon?: IconName; action?: ReactNode }) {
  return (
    <div className="state" data-kind="empty">
      <h3><Icon name={icon} size={18} />{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title = "Konnte nicht geladen werden", children, onRetry }: { title?: string; children?: ReactNode; onRetry?: () => void }) {
  return (
    <div className="state" data-kind="error" role="alert">
      <h3><Lamp state="stop" size="s" />{title}</h3>
      {children && <p>{children}</p>}
      {onRetry && (
        <button type="button" className="btn btn-s" onClick={onRetry}>
          <Icon name="refresh" /> Erneut versuchen
        </button>
      )}
    </div>
  );
}

/* ── Dialog (<dialog> with showModal) ─────────────────────────────── */

export function Dialog({
  open, onClose, title, children, footer, wide, labelledBy,
}: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean; labelledBy?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`dialog${wide ? " dialog-wide" : ""}`}
      aria-labelledby={labelledBy ?? titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      {open && (
        <>
          <header className="dialog-head">
            <h2 id={titleId} style={{ fontSize: "var(--fs-xl)" }}>{title}</h2>
            <button type="button" className="btn btn-quiet btn-icon btn-s" onClick={onClose} aria-label="Schließen">
              <Icon name="close" />
            </button>
          </header>
          <div className="dialog-body">{children}</div>
          {footer && <footer className="dialog-foot">{footer}</footer>}
        </>
      )}
    </dialog>
  );
}

export function ConfirmDialog({
  open, onClose, onConfirm, title, children, confirmLabel, danger, busy,
}: { open: boolean; onClose: () => void; onConfirm: () => void; title: string; children: ReactNode; confirmLabel: string; danger?: boolean; busy?: boolean }) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <button type="button" className="btn" onClick={onClose}>Abbrechen</button>
          <button type="button" className={`btn ${danger ? "btn-danger" : "btn-primary"}`} onClick={onConfirm} disabled={busy} data-busy={busy || undefined}>
            {confirmLabel}
          </button>
        </>
      }
    >
      {children}
    </Dialog>
  );
}

/* ── Popover menu with anchor positioning ─────────────────────────── */

export function Menu({ label, icon = "more", children, align = "end", buttonClass = "btn btn-quiet btn-icon btn-s", text }: {
  label: string; icon?: IconName; children: ReactNode; align?: "start" | "end"; buttonClass?: string; text?: string;
}) {
  const id = useId().replace(/:/g, "");
  const anchor = `--menu-${id}`;
  return (
    <>
      <button
        type="button"
        className={buttonClass}
        popoverTarget={`menu-${id}`}
        aria-label={text ? undefined : label}
        title={text ? undefined : label}
        style={{ anchorName: anchor } as CSSProperties}
      >
        <Icon name={icon} />
        {text}
      </button>
      <div
        id={`menu-${id}`}
        popover="auto"
        className="menu"
        role="menu"
        data-anchored={align}
        style={{ positionAnchor: anchor } as CSSProperties}
        onClick={(event) => {
          if ((event.target as HTMLElement).closest(".menu-item")) (event.currentTarget as HTMLElement).hidePopover();
        }}
      >
        {children}
      </div>
    </>
  );
}

/* ── Gated action: visible but locked for roles without the right ── */

export function lockedTitle(reason: string | null): { disabled?: boolean; title?: string; "aria-describedby"?: string } {
  return reason ? { disabled: true, title: reason } : {};
}

/* ── One-time secret (codes, tokens) ──────────────────────────────── */

export function Secret({ value, label, note, long }: { value: string; label: string; note: ReactNode; long?: boolean }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  return (
    <div className="secret" role="group" aria-label={label}>
      <strong>{label} – wird nur jetzt angezeigt</strong>
      <div className="secret-value">
        <code className={long ? "secret-long" : undefined}>{value}</code>
        <button type="button" className="btn btn-s" onClick={() => void copy()}>
          <Icon name={copied ? "check" : "copy"} /> {copied ? "Kopiert" : "Kopieren"}
        </button>
      </div>
      <p>{note}</p>
      <span className="visually-hidden" aria-live="polite">{copied ? "In die Zwischenablage kopiert" : ""}</span>
    </div>
  );
}

/* ── Copy button ──────────────────────────────────────────────────── */

export function CopyButton({ value, label = "Kopieren" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="btn btn-s"
      onClick={() => {
        void navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        });
      }}
    >
      <Icon name={copied ? "check" : "copy"} /> {copied ? "Kopiert" : label}
    </button>
  );
}

/* ── Reading: number + unit ───────────────────────────────────────── */

export function Reading({ value, unit, digits = 0 }: { value: number | null | undefined; unit: string; digits?: number }) {
  if (value == null || !Number.isFinite(value)) return <span className="reading muted">–</span>;
  const text = new Intl.NumberFormat("de-DE", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
  return (
    <span className="reading">
      {text}
      <span className="unit">{unit}</span>
    </span>
  );
}

export function PageHead({ title, lead, actions, children }: { title: ReactNode; lead?: ReactNode; actions?: ReactNode; children?: ReactNode }) {
  return (
    <header className="page-head">
      <div className="page-head-text">
        <h1>{title}</h1>
        {lead && <p className="lead">{lead}</p>}
        {children}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </header>
  );
}
