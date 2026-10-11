import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "light" | "dark";
const Ctx = createContext<{ theme: Theme; setTheme: (t: Theme) => void; presentation: boolean; setPresentation: (v: boolean) => void }>({
  theme: "light",
  setTheme: () => {},
  presentation: false,
  setPresentation: () => {},
});

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, v: string) {
  try {
    localStorage.setItem(key, v);
  } catch {
    /* хранилище недоступно */
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => (read("sl-theme") as Theme) || "light");
  const [presentation, setPresentation] = useState(() => read("sl-presentation") === "1");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    write("sl-theme", theme);
  }, [theme]);
  useEffect(() => {
    document.documentElement.dataset.presentation = String(presentation);
    write("sl-presentation", presentation ? "1" : "0");
  }, [presentation]);
  return <Ctx.Provider value={{ theme, setTheme, presentation, setPresentation }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);
