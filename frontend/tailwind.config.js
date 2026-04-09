/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          orange: '#ff6b35',
          dark: '#0d1117',
          darker: '#090c10',
          card: '#161b22',
          border: '#30363d',
        },
      },
    },
  },
  plugins: [],
}
