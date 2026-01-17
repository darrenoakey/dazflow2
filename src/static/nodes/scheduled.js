export default {
    id: 'scheduled',
    name: 'Scheduled',
    category: 'Input',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polyline points="12 6 12 12 16 14"/>
    </svg>`,
    defaultData: { interval: 5, unit: 'minutes' },
    getConnectors: () => ({
        inputs: [],
        outputs: [{ id: 'trigger', name: 'trigger' }],
    }),
    getProperties: (data) => [
        { id: 'interval', label: 'Interval', type: 'number', value: data.interval ?? 5, min: 1 },
        { id: 'unit', label: 'Unit', type: 'select', value: data.unit ?? 'minutes', options: [
            { value: 'seconds', label: 'Seconds' },
            { value: 'minutes', label: 'Minutes' },
            { value: 'hours', label: 'Hours' },
            { value: 'days', label: 'Days' },
        ]},
    ],
    canExecute: (inputs) => true,
    execute: (nodeData, inputs) => {
        return [{ time: new Date().toISOString() }];
    },
};
