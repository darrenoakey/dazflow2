export default {
    id: 'append_to_file',
    name: 'Append to File',
    category: 'Output',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="12" y1="18" x2="12" y2="12"/>
        <line x1="9" y1="15" x2="15" y2="15"/>
    </svg>`,
    defaultData: { filepath: '', content: '' },
    getConnectors: () => ({
        inputs: [{ id: 'data', name: 'data' }],
        outputs: [{ id: 'output', name: 'output' }],
    }),
    getProperties: (data) => [
        { id: 'filepath', label: 'File Path', type: 'text', value: data.filepath ?? '' },
        { id: 'content', label: 'Content', type: 'textarea', value: data.content ?? '' },
    ],
    canExecute: (inputs) => true,
    kind: 'array',
};
