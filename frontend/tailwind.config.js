/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surv: {
          bg: '#080b0f',
          panel: '#0f141c',
          panelDark: '#0a0d13',
          card: '#141a24',
          cardHover: '#1a2230',
          border: '#1f2937',
          borderSubtle: '#16202c',
          yellow: '#f59e0b',
          amber: '#fbbf24',
          cyan: '#00e5ff',
          green: '#00e676',
          red: '#ff334b',
          dimRed: '#881337',
          dimGreen: '#064e3b',
          muted: '#64748b',
          dim: '#334155',
          text: '#e2e8f0'
        }
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Share Tech Mono"', 'ui-monospace', 'monospace'],
        display: ['"Chakra Petch"', '"Rajdhani"', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
