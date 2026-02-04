/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'tre-navy': '#0e2431',
        'tre-teal': '#90c5ce',
        'tre-brown-dark': '#5b4825',
        'tre-brown-medium': '#775723',
        'tre-brown-light': '#966e35',
        'tre-tan': '#cab487',
      },
      fontFamily: {
        'oswald': ['Oswald', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
