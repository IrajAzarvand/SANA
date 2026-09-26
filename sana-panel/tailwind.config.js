/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-base':      '#0B1220',
        'bg-elevated':  '#111A2E',
        'bg-overlay':   '#16213A',
        'bg-hover':     '#1B2848',
        'border-base':   '#1F2D4D',
        'border-strong': '#2A3B5F',
        'text-primary':   '#E8EDF7',
        'text-secondary': '#9BA8C4',
        'text-muted':     '#5F6E8F',
        'brand': {
          400: '#2DD4BF',
          500: '#14B8A6',
          600: '#0D9488',
          900: '#134E4A',
        },
        'success': '#10B981',
        'warning': '#F59E0B',
        'danger':  '#EF4444',
        'info':    '#3B82F6',
      },
      fontFamily: {
        sans: ['Vazirmatn', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        'card': '16px',
        'field': '10px',
      },
    },
  },
  plugins: [],
}
