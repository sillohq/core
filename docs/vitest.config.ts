import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        include: ['test/**/*.test.ts'],
        environment: 'node',
        coverage: {
            provider: 'v8',
            reporter: ['text', 'lcov'],
            reportsDirectory: 'coverage',
            include: ['packages/lucode-starlight/**/*.{ts,tsx,mts,cts}'],
            exclude: [
                '**/*.d.ts',
                '**/*.test.ts',
                'packages/lucode-starlight/index.ts',
                'packages/lucode-starlight/user-components.ts',
                'packages/lucode-starlight/components/custom/dropdown/index.ts',
            ],
            thresholds: {
                perFile: true,
                statements: 95,
                branches: 80,
                functions: 95,
                lines: 97,
            },
        },
    },
});
