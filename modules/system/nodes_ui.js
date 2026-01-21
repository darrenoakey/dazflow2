// System module node UI definitions
// These define the frontend presentation of system interaction nodes

export const nodeTypes = [
    // Dialog node - simple OK dialog
    {
        id: 'dialog',
        name: 'Dialog',
        category: 'System',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <line x1="3" y1="9" x2="21" y2="9"/>
            <circle cx="12" cy="15" r="2"/>
        </svg>`,
        defaultData: { message: '', title: 'Dazflow' },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'out', name: 'out' }],
        }),
        getProperties: (data) => [
            { id: 'title', label: 'Title', type: 'text', value: data.title ?? 'Dazflow' },
            { id: 'message', label: 'Message', type: 'textarea', value: data.message ?? '' },
        ],
    },

    // Prompt node - dialog with customizable buttons and optional input
    {
        id: 'prompt',
        name: 'Prompt',
        category: 'System',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <line x1="3" y1="9" x2="21" y2="9"/>
            <path d="M9 15h6"/>
            <path d="M12 15v3"/>
        </svg>`,
        defaultData: {
            message: '',
            title: 'Dazflow',
            buttons: 'OK,Cancel',
            showInput: false,
            defaultInput: ''
        },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'out', name: 'out' }],
        }),
        getProperties: (data) => [
            { id: 'title', label: 'Title', type: 'text', value: data.title ?? 'Dazflow' },
            { id: 'message', label: 'Message', type: 'textarea', value: data.message ?? '' },
            { id: 'buttons', label: 'Buttons', type: 'text', value: data.buttons ?? 'OK,Cancel',
              placeholder: 'Comma-separated button labels' },
            { id: 'showInput', label: 'Show Text Input', type: 'boolean', value: data.showInput ?? false },
            { id: 'defaultInput', label: 'Default Input Value', type: 'text', value: data.defaultInput ?? '' },
        ],
    },

    // Notification node - non-blocking system notification
    {
        id: 'notification',
        name: 'Notification',
        category: 'System',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>`,
        defaultData: { message: '', title: 'Dazflow' },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'out', name: 'out' }],
        }),
        getProperties: (data) => [
            { id: 'title', label: 'Title', type: 'text', value: data.title ?? 'Dazflow' },
            { id: 'message', label: 'Message', type: 'textarea', value: data.message ?? '' },
        ],
    },
];
