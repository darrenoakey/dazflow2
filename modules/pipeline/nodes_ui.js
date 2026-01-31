// Pipeline module node UI definitions
// State-based workflow nodes for idempotent data pipelines
//
// These nodes enable:
// - Triggering on state changes (new/updated files)
// - Reading and writing states with change tracking
// - Conditional logic based on state existence
// - Listing entities for batch processing

export const nodeTypes = [
    // State Trigger node
    {
        id: 'state_trigger',
        name: 'State Trigger',
        category: 'Pipeline',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
            <polyline points="22,6 12,13 2,6"/>
            <circle cx="18" cy="18" r="3" fill="currentColor"/>
        </svg>`,
        defaultData: {
            state_root: 'output/',
            pattern: 'input/{id}/',
            scan_interval: 60,
        },
        getConnectors: () => ({
            inputs: [],
            outputs: [{ id: 'entity', name: 'entity' }],
        }),
        getProperties: (data) => [
            {
                id: 'state_root',
                label: 'State Root',
                type: 'text',
                value: data.state_root ?? 'output/',
                placeholder: 'output/',
                instructions: 'Root directory for state files (relative to data directory)',
            },
            {
                id: 'pattern',
                label: 'Pattern',
                type: 'text',
                value: data.pattern ?? '',
                placeholder: 'input/{date}/',
                instructions: 'Use {variable} for entity ID extraction (e.g., logs/{date}/, items/{feed}/{guid})',
            },
            {
                id: 'scan_interval',
                label: 'Scan Interval (seconds)',
                type: 'number',
                value: data.scan_interval ?? 60,
                min: 5,
                max: 3600,
            },
        ],
        execute: (nodeData) => {
            return [{
                entity_id: 'manual-trigger',
                pattern: nodeData.pattern,
                triggered_at: new Date().toISOString(),
            }];
        },
    },

    // State Read node
    {
        id: 'state_read',
        name: 'State Read',
        category: 'Pipeline',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>`,
        defaultData: {
            state_root: 'output/',
            pattern: '',
            entity_id: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'content', name: 'content' }],
        }),
        getProperties: (data) => [
            {
                id: 'state_root',
                label: 'State Root',
                type: 'text',
                value: data.state_root ?? 'output/',
            },
            {
                id: 'pattern',
                label: 'Pattern',
                type: 'text',
                value: data.pattern ?? '',
                placeholder: 'summaries/{date}.txt',
                instructions: 'State pattern to read. Use {{ $.entity_id }} in entity_id field.',
            },
            {
                id: 'entity_id',
                label: 'Entity ID',
                type: 'text',
                value: data.entity_id ?? '',
                placeholder: '{{ $.entity_id }}',
                instructions: 'Leave empty to use entity_id from input data.',
            },
        ],
    },

    // State Write node
    {
        id: 'state_write',
        name: 'State Write',
        category: 'Pipeline',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <line x1="9" y1="15" x2="15" y2="15"/>
        </svg>`,
        defaultData: {
            state_root: 'output/',
            pattern: '',
            entity_id: '',
            content: '',
            min_size: 0,
        },
        getConnectors: () => ({
            inputs: [{ id: 'data', name: 'data' }],
            outputs: [{ id: 'result', name: 'result' }],
        }),
        getProperties: (data) => [
            {
                id: 'state_root',
                label: 'State Root',
                type: 'text',
                value: data.state_root ?? 'output/',
            },
            {
                id: 'pattern',
                label: 'Pattern',
                type: 'text',
                value: data.pattern ?? '',
                placeholder: 'output/{date}.json',
                instructions: 'Where to write the state file.',
            },
            {
                id: 'entity_id',
                label: 'Entity ID',
                type: 'text',
                value: data.entity_id ?? '',
                placeholder: '{{ $.entity_id }}',
                instructions: 'Leave empty to use entity_id from input.',
            },
            {
                id: 'content',
                label: 'Content',
                type: 'textarea',
                value: data.content ?? '',
                placeholder: '{{ $.result }}',
                instructions: 'Content to write. Leave empty to use input data.',
            },
            {
                id: 'min_size',
                label: 'Min Size',
                type: 'number',
                value: data.min_size ?? 0,
                min: 0,
                instructions: 'Minimum content size (fails if smaller).',
            },
        ],
    },

    // State Check node
    {
        id: 'state_check',
        name: 'State Check',
        category: 'Pipeline',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <path d="M9 15l2 2 4-4"/>
        </svg>`,
        defaultData: {
            state_root: 'output/',
            pattern: '',
            entity_id: '',
            check_staleness: false,
        },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [
                { id: 'exists', name: 'exists' },
                { id: 'missing', name: 'missing' },
            ],
        }),
        getProperties: (data) => [
            {
                id: 'state_root',
                label: 'State Root',
                type: 'text',
                value: data.state_root ?? 'output/',
            },
            {
                id: 'pattern',
                label: 'Pattern',
                type: 'text',
                value: data.pattern ?? '',
                placeholder: 'processed/{date}.json',
            },
            {
                id: 'entity_id',
                label: 'Entity ID',
                type: 'text',
                value: data.entity_id ?? '',
                placeholder: '{{ $.entity_id }}',
            },
            {
                id: 'check_staleness',
                label: 'Check Staleness',
                type: 'select',
                value: data.check_staleness ?? false,
                options: [
                    { value: false, label: 'No (existence only)' },
                    { value: true, label: 'Yes (also check if stale)' },
                ],
            },
        ],
    },

    // State List node
    {
        id: 'state_list',
        name: 'State List',
        category: 'Pipeline',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="8" y1="6" x2="21" y2="6"/>
            <line x1="8" y1="12" x2="21" y2="12"/>
            <line x1="8" y1="18" x2="21" y2="18"/>
            <line x1="3" y1="6" x2="3.01" y2="6"/>
            <line x1="3" y1="12" x2="3.01" y2="12"/>
            <line x1="3" y1="18" x2="3.01" y2="18"/>
        </svg>`,
        defaultData: {
            state_root: 'output/',
            pattern: '',
            include_stale_only: false,
        },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'entities', name: 'entities' }],
        }),
        getProperties: (data) => [
            {
                id: 'state_root',
                label: 'State Root',
                type: 'text',
                value: data.state_root ?? 'output/',
            },
            {
                id: 'pattern',
                label: 'Pattern',
                type: 'text',
                value: data.pattern ?? '',
                placeholder: 'items/{id}.json',
                instructions: 'Pattern to scan for entities.',
            },
            {
                id: 'include_stale_only',
                label: 'Filter',
                type: 'select',
                value: data.include_stale_only ?? false,
                options: [
                    { value: false, label: 'All entities' },
                    { value: true, label: 'Stale entities only' },
                ],
            },
        ],
    },

    // State Clear Failure node
    {
        id: 'state_clear_failure',
        name: 'Clear Failure',
        category: 'Pipeline',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M15 9l-6 6"/>
            <path d="M9 9l6 6"/>
        </svg>`,
        defaultData: {
            state_root: 'output/',
            pattern: '',
            entity_id: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'result', name: 'result' }],
        }),
        getProperties: (data) => [
            {
                id: 'state_root',
                label: 'State Root',
                type: 'text',
                value: data.state_root ?? 'output/',
            },
            {
                id: 'pattern',
                label: 'Pattern',
                type: 'text',
                value: data.pattern ?? '',
                placeholder: 'output/{date}.json',
            },
            {
                id: 'entity_id',
                label: 'Entity ID',
                type: 'text',
                value: data.entity_id ?? '',
                placeholder: '{{ $.entity_id }}',
            },
        ],
    },
];
