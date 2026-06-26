import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0F0F13",
          surface: "#16161E",
          elevated: "#1E1E2A",
          overlay: "#252532",
        },
        border: {
          DEFAULT: "#2A2A3A",
          subtle: "#1E1E2A",
          strong: "#3A3A4E",
        },
        primary: {
          DEFAULT: "#7C3AED",
          hover: "#6D28D9",
          muted: "#7C3AED33",
          light: "#A78BFA",
        },
        accent: {
          DEFAULT: "#06B6D4",
          muted: "#06B6D433",
        },
        success: {
          DEFAULT: "#10B981",
          muted: "#10B98133",
          light: "#6EE7B7",
        },
        warning: {
          DEFAULT: "#F59E0B",
          muted: "#F59E0B33",
          light: "#FCD34D",
        },
        danger: {
          DEFAULT: "#EF4444",
          muted: "#EF444433",
          light: "#FCA5A5",
        },
        text: {
          DEFAULT: "#E2E8F0",
          muted: "#94A3B8",
          dim: "#64748B",
          inverse: "#0F0F13",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.2s ease-in-out",
        "slide-in": "slideIn 0.3s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideIn: {
          "0%": { transform: "translateY(8px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
