/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#000000',
        panel: '#1C1C1E',
        line: '#2C2C2F',
        slate: '#708090',
        silver: '#C0C0C0',
        crisp: '#FFFFFF',
        violetAccent: '#6C5CE7',
        tealAccent: '#14B8A6',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
