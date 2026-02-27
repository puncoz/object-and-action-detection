/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                // Industrial dark theme colors
                industrial: {
                    bg: '#0f1419',
                    surface: '#1a1f26',
                    border: '#2d3640',
                    text: '#e6edf3',
                    muted: '#8b949e',
                    accent: '#58a6ff',
                    success: '#3fb950',
                    warning: '#d29922',
                    danger: '#f85149',
                },
            },
            fontFamily: {
                mono: ['JetBrains Mono', 'Menlo', 'Monaco', 'monospace'],
            },
        },
    },
    plugins: [],
}
