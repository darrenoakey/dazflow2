export default {
    id: 'start',
    name: 'Start',
    category: 'Input',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"/>
    </svg>`,
    defaultData: {},
    getConnectors: () => ({
        inputs: [],
        outputs: [{ id: 'out', name: 'out' }],
    }),
    getProperties: () => [],
};
