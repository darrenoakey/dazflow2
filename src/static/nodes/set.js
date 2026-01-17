export default {
    id: 'set',
    name: 'Set',
    category: 'Transform',
    // Map nodes receive a single item, return a single item
    // The infrastructure handles iteration over arrays
    kind: 'map',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 20h9"/>
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
    </svg>`,
    defaultData: { fields: [] },
    getConnectors: () => ({
        inputs: [{ id: 'data', name: 'data' }],
        outputs: [{ id: 'output', name: 'output' }],
    }),
    getProperties: (data) => [
        { id: 'fields', label: 'Output Fields', type: 'fieldlist', value: data.fields ?? [] },
    ],
    canExecute: (inputs) => true,
    // For map nodes: execute receives a single item, returns a single item
    execute: (nodeData, item) => {
        const result = {};
        const fields = nodeData.fields || [];
        for (const field of fields) {
            if (field.name) {
                let value = field.value;
                try {
                    value = JSON.parse(field.value);
                } catch (e) {
                    // Keep as string if not valid JSON
                }
                result[field.name] = value;
            }
        }
        return result;
    },
};
