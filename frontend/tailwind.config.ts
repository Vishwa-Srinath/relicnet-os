import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg:     "#05070d",
        panel:  "#0b1020",
        accent: "#22d3ee",
        ok:     "#10b981",
        warn:   "#f59e0b",
        bad:    "#ef4444",
      },
      fontFamily: { mono: ["JetBrains Mono", "Courier New", "monospace"] },
    },
  },
  plugins: [],
} satisfies Config;
