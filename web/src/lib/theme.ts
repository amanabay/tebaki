import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "tebaki-theme";

function initial(): Theme {
  const stored = localStorage.getItem(KEY);
  if (stored === "light" || stored === "dark") return stored;
  return "dark";
}

/** Apply theme with transition suppression to avoid a smeared flip. */
function apply(theme: Theme) {
  const root = document.documentElement;
  const suppress = document.createElement("style");
  suppress.textContent = "*,*::before,*::after{transition:none !important}";
  document.head.appendChild(suppress);
  root.classList.toggle("dark", theme === "dark");
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#1d1a17" : "#f5f1e9");
  // force reflow, then restore transitions next frame
  void root.offsetHeight;
  requestAnimationFrame(() => requestAnimationFrame(() => suppress.remove()));
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(initial);

  useEffect(() => {
    apply(theme);
    localStorage.setItem(KEY, theme);
  }, [theme]);

  return { theme, toggle: () => setTheme((t) => (t === "light" ? "dark" : "light")) };
}
