import { useCallback, useEffect, useState } from "react";

export type Theme = "auto" | "light" | "dark";
const KEY = "ncc-theme"; // display preference only, no secret

function read(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "auto";
  } catch {
    return "auto";
  }
}

function apply(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "auto") root.removeAttribute("data-theme");
  else root.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]:not([media])');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#20262d" : "#e3e9e1");
}

apply(read());

export function useTheme(): { theme: Theme; cycle: () => void } {
  const [theme, setTheme] = useState<Theme>(read);
  useEffect(() => {
    apply(theme);
    try {
      if (theme === "auto") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, theme);
    } catch {
      /* storage blocked: preference lasts for this visit */
    }
  }, [theme]);
  const cycle = useCallback(() => setTheme((current) => (current === "auto" ? "light" : current === "light" ? "dark" : "auto")), []);
  return { theme, cycle };
}
