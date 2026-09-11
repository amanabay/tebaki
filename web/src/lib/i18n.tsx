import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Language = "en" | "am";

const COPY: Record<Language, Record<string, string>> = {
  en: {
    map: "Overview",
    ledger: "Cases",
    watch: "Watching",
    stats: "Insights",
    report: "Report issue",
    decisions: "Review",
    switchLanguage: "አማርኛ",
    guardian: "the city's guardian",
    footer: "files, tracks & escalates so you don't have to",
  },
  am: {
    map: "ካርታ",
    ledger: "መዝገብ",
    watch: "ክትትል",
    stats: "ስታቲስቲክስ",
    report: "ሪፖርት",
    decisions: "ውሳኔዎች",
    switchLanguage: "English",
    guardian: "የከተማዋ ጠባቂ",
    footer: "ያለርስዎ ክትትል ይመዘግባል፣ ይከታተላል፣ ያሳድጋል",
  },
};

type LanguageContextValue = { language: Language; setLanguage: (language: Language) => void; t: (key: string) => string };
const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => {
    const saved = window.localStorage.getItem("tebaki-language");
    return saved === "am" ? "am" : "en";
  });
  const setLanguage = (next: Language) => {
    setLanguageState(next);
    window.localStorage.setItem("tebaki-language", next);
  };
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);
  const value = useMemo(() => ({ language, setLanguage, t: (key: string) => COPY[language][key] ?? COPY.en[key] ?? key }), [language]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage(): LanguageContextValue {
  const value = useContext(LanguageContext);
  if (!value) throw new Error("useLanguage must be used inside LanguageProvider");
  return value;
}
