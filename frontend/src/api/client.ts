/**
 * Same-origin fetch with the HttpOnly session cookie. The legacy dashboard
 * token is optional, lives in memory only and is sent only when set.
 */

const BASE = "/api/v1";

let legacyToken: string | null = null;
let unauthorizedHandler: (() => void) | null = null;

export function setLegacyToken(token: string | null): void {
  legacyToken = token && token.trim() ? token.trim() : null;
}

export function hasLegacyToken(): boolean {
  return legacyToken !== null;
}

/** Called once for any 401 outside the login requests themselves. */
export function onUnauthorized(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  get offline(): boolean {
    return this.status === 0;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  json?: unknown;
  body?: BodyInit;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** Login/registration: a 401 is a wrong password, not an expired session. */
  authRequest?: boolean;
  /** Return the raw Response (artwork, attachments). */
  raw?: boolean;
}

export function authHeaders(): Record<string, string> {
  return legacyToken ? { "X-NCC-Dashboard-Token": legacyToken } : {};
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...authHeaders(), ...options.headers };
  let body = options.body;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  }
  let response: Response;
  try {
    response = await fetch(BASE + path, {
      method: options.method ?? "GET",
      headers,
      body,
      credentials: "same-origin",
      signal: options.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "Server nicht erreichbar");
  }
  if (!response.ok) {
    const detail = await readDetail(response);
    if (response.status === 401 && !options.authRequest) unauthorizedHandler?.();
    throw new ApiError(response.status, detail);
  }
  if (options.raw) return response as T;
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((item) => (item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : String(item)))
          .join(" · ");
      }
    }
  } catch {
    /* body was not JSON */
  }
  return response.statusText;
}

/** German, user-facing text for an error, with known server details translated. */
export function describeError(error: unknown, fallback = "Das hat nicht geklappt."): string {
  if (!(error instanceof ApiError)) return fallback;
  if (error.offline) return "Server nicht erreichbar. Prüfe Tailscale oder das lokale Netz und versuche es erneut.";
  const known: Record<string, string> = {
    "invalid username or password": "Benutzername oder Passwort stimmt nicht.",
    "invalid or expired admin code": "Der Code ist ungültig, schon benutzt oder abgelaufen.",
    "invite code is invalid or expired": "Der Einladungscode ist ungültig oder abgelaufen.",
    "username already exists": "Diesen Benutzernamen gibt es schon.",
    "current password is incorrect": "Das aktuelle Passwort stimmt nicht.",
    "a personal account is required": "Dafür brauchst du ein persönliches Konto (keine Admin-Code-Sitzung).",
    "commander access required": "Nur Commander dürfen das.",
    "not available for friend accounts": "Für Freundes-Konten nicht verfügbar.",
    "cannot deactivate your own account": "Du kannst dein eigenes Konto nicht deaktivieren.",
    "at least one active commander is required": "Es muss mindestens ein aktiver Commander bleiben.",
    "pairing request not found": "Die Kopplungsanfrage wurde nicht gefunden oder ist bereits erledigt.",
    "pairing request expired": "Die Kopplungsanfrage ist abgelaufen. Öffne am Gerät im NCC-Symbol „Gerät koppeln…“ für einen neuen Link.",
    "device belongs to another account": "Dieses Gerät gehört zu einem anderen Konto und kann nicht übernommen werden.",
    "revoke an invitation before removing it from the list": "Widerrufe die Einladung, bevor du sie entfernst.",
    "image too large": "Das Bild ist zu groß.",
    "use a JPEG, PNG or WebP image": "Bitte ein JPEG-, PNG- oder WebP-Bild verwenden.",
    "node or compatible release not found": "Kein passendes Release für dieses Gerät gefunden.",
    "no Telegram chat linked": "Es ist noch kein Telegram-Chat verknüpft.",
  };
  if (known[error.detail]) return known[error.detail]!;
  if (error.status === 403) return "Dafür fehlen dir die Rechte.";
  if (error.status === 404) return "Nicht gefunden – vielleicht wurde es gerade entfernt.";
  if (error.status === 429) return "Zu viele Versuche. Warte einen Moment.";
  if (error.status >= 500) return error.detail && /[äöüß]|ist|nicht/.test(error.detail) ? error.detail : "Der Server hatte ein Problem. Versuche es gleich noch einmal.";
  if (error.status === 422) return `Eingabe abgelehnt: ${error.detail}`;
  return error.detail || fallback;
}
