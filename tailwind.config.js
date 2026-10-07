/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#0f4c81', light: '#3b82c4' },
        alarm: { high: '#d32f2f', medium: '#f9a825', low: '#0288d1' },
      },
    },
  },
  plugins: [],
};
