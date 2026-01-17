// PostgreSQL module node UI definitions

export const nodeTypes = [
    {
        id: 'postgres_query',
        name: 'Query',
        category: 'Database',
        kind: 'array',
        requiredCredential: 'postgres',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <ellipse cx="12" cy="5" rx="9" ry="3"/>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            <path d="M3 12v7c0 1.66 4 3 9 3s9-1.34 9-3v-7"/>
        </svg>`,
        defaultData: { query: 'SELECT 1' },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'rows', name: 'rows' }],
        }),
        getProperties: (data) => [
            {
                id: 'query',
                label: 'SQL Query',
                type: 'textarea',
                value: data.query ?? 'SELECT 1',
            },
        ],
    },
];
