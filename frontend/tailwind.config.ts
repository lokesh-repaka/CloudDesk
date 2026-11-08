import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: "#070d10",
          canvas: "#091216",
          sidebar: "#050a0c",
          card: "#0e181c",
          "card-elevated": "#122026",
          "card-hover": "#15252c",
          border: "#182c34",
          "border-subtle": "#112026",
          input: "#0d1a1f",
        },
        brand: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#00d2b4",
          700: "#0f766e",
          800: "#115e59",
          900: "#134e4a",
          accent: "#00d2b4",
        },
      },
      fontSize: {
        "3xs": ["0.625rem", { lineHeight: "0.85rem" }],
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgba(0, 0, 0, 0.4)",
        card: "0 2px 6px -1px rgba(0, 0, 0, 0.4), 0 1px 3px -1px rgba(0, 0, 0, 0.3)",
        "card-hover": "0 8px 16px -2px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.4)",
        glow: "0 0 15px -3px rgba(0, 210, 180, 0.2)",
        "glow-emerald": "0 0 15px -3px rgba(16, 185, 129, 0.2)",
        "glow-amber": "0 0 15px -3px rgba(245, 158, 11, 0.2)",
      },
    },
  },
  plugins: [],
};

export default config;
