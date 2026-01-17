export default {
    id: 'http',
    name: 'HTTP',
    category: 'Action',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <path d="M2 12h20"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>`,
    defaultData: { url: '', method: 'GET' },
    getConnectors: () => ({
        inputs: [{ id: 'trigger', name: 'trigger' }],
        outputs: [
            { id: 'success', name: 'success' },
            { id: 'error', name: 'error' },
        ],
    }),
    getProperties: (data) => [
        { id: 'method', label: 'Method', type: 'select', value: data.method ?? 'GET', options: [
            { value: 'GET', label: 'GET' },
            { value: 'POST', label: 'POST' },
            { value: 'PUT', label: 'PUT' },
            { value: 'DELETE', label: 'DELETE' },
            { value: 'PATCH', label: 'PATCH' },
        ]},
        { id: 'url', label: 'URL', type: 'text', value: data.url ?? '', placeholder: 'https://api.example.com/endpoint' },
    ],
};
