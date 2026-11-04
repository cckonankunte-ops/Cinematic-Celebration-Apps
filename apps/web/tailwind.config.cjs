/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx,md,mdx}'],
  theme: {
    extend: {
      colors: {
        // Core brand (purple) kept for continuity.
        brand: {
          DEFAULT: '#7c2d92',
          dark: '#4a1659',
          light: '#a855c7',
        },
        // Festive accents used across gradients, badges, and highlights.
        festive: {
          pink: '#ec4899',
          magenta: '#d6207e',
          gold: '#f59e0b',
          orange: '#fb7185',
          mint: '#34d399',
        },
      },
      backgroundImage: {
        // Reusable celebration gradients.
        'festive-hero':
          'linear-gradient(120deg, #7c2d92 0%, #d6207e 45%, #fb7185 75%, #f59e0b 100%)',
        'festive-soft':
          'linear-gradient(135deg, #faf5ff 0%, #fdf2f8 50%, #fff7ed 100%)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        'gradient-shift': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
        pop: {
          '0%': { transform: 'scale(0.9)', opacity: '0' },
          '60%': { transform: 'scale(1.03)' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.6s ease-out both',
        float: 'float 4s ease-in-out infinite',
        'gradient-shift': 'gradient-shift 12s ease infinite',
        pop: 'pop 0.4s ease-out both',
      },
    },
  },
  plugins: [],
};
