import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        // Look for any .test.js or .test.ts file inside the frontend/
        include: ['**/*.test.js'],
        exclude: [
            '**/node_modules/**',
            '**/dist/**',
            '**/Test_Database_4/**',
            '**/.PIlocvenv/**'
        ],
        globals: true,
        environment: 'jsdom',
        coverage: {
            reporter: ['text', 'html'],
            exclude: ['**/*.test.js']
        },
    },
});