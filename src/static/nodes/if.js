export default {
    id: 'if',
    name: 'IF',
    category: 'Logic',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 3L21 12L12 21L3 12L12 3Z"/>
        <path d="M12 8v4"/>
        <circle cx="12" cy="15" r="0.5" fill="currentColor"/>
    </svg>`,
    defaultData: { condition: '' },
    getConnectors: () => ({
        inputs: [{ id: 'input', name: 'input' }],
        outputs: [
            { id: 'true', name: 'true' },
            { id: 'false', name: 'false' },
        ],
    }),
    getProperties: (data) => [
        { id: 'condition', label: 'Condition', type: 'text', value: data.condition ?? '', placeholder: 'e.g. item.value > 10' },
    ],
};
