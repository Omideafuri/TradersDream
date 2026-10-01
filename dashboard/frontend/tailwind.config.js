/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0b0e14',
        card: '#111722',
        'card-border': '#1e293b',
        'panel-header': '#0f172a',
        'terminal-dark': '#06090e',
        'accent-green': '#10b981',
        'accent-red': '#ef4444',
        'accent-cyan': '#06b6d4',
        'accent-amber': '#f59e0b',
        'accent-purple': '#8b5cf6',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', '"Liberation Mono"', '"Courier New"', 'monospace'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
