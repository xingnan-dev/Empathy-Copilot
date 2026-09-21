import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        pearl: '#f4f0e9',
        ivory: '#faf8f3',
        bone: '#e9e1d6',
        ink: '#19191b',
        warm: '#69655f',
        mist: '#918b83',
        coral: '#d96d5c',
        iris: '#7068b5',
        cyan: '#438f91',
      },
      fontFamily: {
        sans: ['Inter', 'Avenir Next', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
        display: ['Iowan Old Style', 'Baskerville', 'Songti SC', 'Times New Roman', 'serif'],
      },
    },
  },
  plugins: [],
} satisfies Config
