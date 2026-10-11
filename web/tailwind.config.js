/** Tailwind поверх CSS-переменных токенов (src/design/tokens.css). */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    screens: { sm: "640px", md: "768px", lg: "1024px", xl: "1280px" },
    extend: {
      colors: {
        bg: "var(--bg)", surface: "var(--surface)", sunken: "var(--surface-sunken)",
        line: "var(--border)", "line-strong": "var(--border-strong)",
        ink: "var(--text)", ink2: "var(--text-2)", ink3: "var(--text-3)",
        primary: "var(--primary)", "primary-hover": "var(--primary-hover)", "primary-soft": "var(--primary-soft)",
        "primary-soft-2": "var(--primary-soft-2)", "on-primary": "var(--on-primary)", link: "var(--link)",
        success: "var(--success)", "success-bg": "var(--success-bg)", warning: "var(--warning)",
        "warning-bg": "var(--warning-bg)", danger: "var(--danger)", "danger-bg": "var(--danger-bg)",
        neutral: "var(--neutral)", "neutral-bg": "var(--neutral-bg)",
      },
      borderRadius: { card: "var(--r-card)", panel: "var(--r-panel)", control: "var(--r-control)" },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["ui-monospace", "Consolas", "monospace"] },
      fontSize: {
        display: ["40px", { lineHeight: "48px", letterSpacing: "-0.02em", fontWeight: "600" }],
        h1: ["28px", { lineHeight: "36px", letterSpacing: "-0.01em", fontWeight: "600" }],
        h2: ["20px", { lineHeight: "28px", fontWeight: "600" }],
        body: ["16px", { lineHeight: "24px" }],
        small: ["14px", { lineHeight: "20px" }],
        caption: ["13px", { lineHeight: "18px" }],
      },
      maxWidth: { container: "1280px" },
      transitionDuration: { DEFAULT: "180ms" },
    },
  },
  plugins: [],
};
