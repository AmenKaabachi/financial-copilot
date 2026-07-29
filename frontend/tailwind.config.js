/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#EBF0FF',
          100: '#D6E0FF',
          200: '#ADC1FF',
          300: '#85A2FF',
          400: '#5C83FF',
          500: '#2F5FE0',
          600: '#254BB3',
          700: '#1C3786',
          800: '#122459',
          900: '#09122D',
        },
        success: '#22C55E',
        danger: '#EF4444',
        warning: '#F59E0B',
      },
      animation: {
        'fadeIn': 'fadeIn 0.2s ease-in-out',
        'slideUp': 'slideUp 0.25s ease-in-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
