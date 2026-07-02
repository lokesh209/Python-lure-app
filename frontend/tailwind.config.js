/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f7f8",
          100: "#eeeef0",
          200: "#d8d8de",
          300: "#b6b6c0",
          400: "#88889a",
          500: "#5e5e74",
          600: "#43435a",
          700: "#323247",
          800: "#1f1f30",
          900: "#13131e",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Inter",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
