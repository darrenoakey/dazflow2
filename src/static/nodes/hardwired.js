export default {
    id: 'hardwired',
    name: 'Hardwired',
    category: 'Input',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="4" y="4" width="16" height="16" rx="2"/>
        <path d="M9 9h6"/>
        <path d="M9 12h6"/>
        <path d="M9 15h4"/>
    </svg>`,
    defaultData: {
        json: JSON.stringify([
            { name: "Sir Barksalot", woofs: 9001 },
            { name: "Professor Whiskers", naps: 42 },
            { name: "Captain Fluffypants", treats: 1337 }
        ], null, 2)
    },
    getConnectors: () => ({
        inputs: [],
        outputs: [{ id: 'data', name: 'data' }],
    }),
    getProperties: (data) => [
        { id: 'json', label: 'JSON Data', type: 'textarea', value: data.json ?? '[]' },
    ],
    canExecute: () => true,
    execute: (nodeData) => {
        try {
            return JSON.parse(nodeData.json || '[]');
        } catch (e) {
            return [{ error: 'Invalid JSON', message: e.message }];
        }
    },
};
