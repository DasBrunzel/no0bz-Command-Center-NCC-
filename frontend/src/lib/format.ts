const nf0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const compact = new Intl.NumberFormat("de-DE", { notation: "compact", maximumFractionDigits: 1 });
const rtf = new Intl.RelativeTimeFormat("de-DE", { numeric: "auto" });
const dateTime = new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
const timeOnly = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const dayShort = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "numeric" });

export function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function fmtInt(value: number | null | undefined): string {
  return value == null ? "–" : nf0.format(value);
}

export function fmt1(value: number | null | undefined): string {
  return value == null ? "–" : nf1.format(value);
}

export function fmtCompact(value: number | null | undefined): string {
  return value == null ? "–" : compact.format(value);
}

export function fmtPercent(value: number | null | undefined): string {
  return value == null ? "–" : `${nf0.format(value)} %`;
}

export function fmtBytes(bytes: number | null | undefined): string {
  if (bytes == null) return "–";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (Math.abs(value) >= 1000 && unit < units.length - 1) {
    value /= 1000;
    unit += 1;
  }
  return `${unit === 0 ? nf0.format(value) : nf1.format(value)} ${units[unit]}`;
}

export function fmtGb(gb: number | null | undefined): string {
  if (gb == null) return "–";
  return gb >= 1000 ? `${nf1.format(gb / 1000)} TB` : `${gb >= 100 ? nf0.format(gb) : nf1.format(gb)} GB`;
}

export function fmtMbps(value: number | null | undefined): string {
  if (value == null) return "–";
  return value >= 100 ? `${nf0.format(value)} Mbit/s` : `${nf1.format(value)} Mbit/s`;
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "–";
  const s = Math.max(0, Math.round(seconds));
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  if (days > 0) return `${days} T ${hours} h`;
  if (hours > 0) return `${hours} h ${minutes.toString().padStart(2, "0")} min`;
  if (minutes > 0) return `${minutes} min`;
  return `${s} s`;
}

export function fmtHours(seconds: number): string {
  const hours = seconds / 3600;
  return hours >= 10 ? `${nf0.format(hours)} h` : `${nf1.format(hours)} h`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "–";
}

export function fmtDate(iso: string | null | undefined): string {
  return iso ? dateOnly.format(new Date(iso)) : "–";
}

export function fmtTime(iso: string | Date | null | undefined): string {
  return iso ? timeOnly.format(typeof iso === "string" ? new Date(iso) : iso) : "–";
}

export function fmtDay(isoDate: string): string {
  return dayShort.format(new Date(`${isoDate}T12:00:00`));
}

/** "vor 3 Minuten", "gestern", "in 12 Minuten". */
export function fmtRelative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "nie";
  const diff = (new Date(iso).getTime() - now) / 1000;
  const abs = Math.abs(diff);
  if (abs < 45) return diff < 0 ? "gerade eben" : "gleich";
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), "day");
  return fmtDate(iso);
}

export function minutesUntil(iso: string | null | undefined, now = Date.now()): number {
  if (!iso) return 0;
  return Math.max(0, Math.round((new Date(iso).getTime() - now) / 60000));
}

export function plural(count: number, one: string, many: string): string {
  return `${nf0.format(count)} ${count === 1 ? one : many}`;
}
