import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { describeError } from "../api/client";
import { Lamp } from "./ui";
import { Icon } from "./Icon";

type Tone = "go" | "caution" | "stop" | "shunt";
interface ToastItem { id: number; tone: Tone; text: string }

interface ToastApi {
  ok: (text: string) => void;
  fail: (error: unknown, fallback?: string) => void;
  notify: (text: string, tone?: Tone) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const dismiss = useCallback((id: number) => setItems((list) => list.filter((item) => item.id !== id)), []);
  const notify = useCallback((text: string, tone: Tone = "go") => {
    const id = ++counter;
    setItems((list) => [...list.slice(-3), { id, tone, text }]);
    setTimeout(() => dismiss(id), tone === "stop" ? 9000 : 5000);
  }, [dismiss]);
  const api = useMemo<ToastApi>(() => ({
    notify,
    ok: (text) => notify(text, "go"),
    fail: (error, fallback) => notify(describeError(error, fallback), "stop"),
  }), [notify]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts" aria-live="polite" aria-relevant="additions">
        {items.map((item) => (
          <div className="toast" key={item.id} role={item.tone === "stop" ? "alert" : "status"}>
            <Lamp state={item.tone} size="s" />
            <p>{item.text}</p>
            <button type="button" className="btn btn-quiet btn-icon btn-s" onClick={() => dismiss(item.id)} aria-label="Meldung schließen">
              <Icon name="close" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast outside ToastProvider");
  return value;
}
