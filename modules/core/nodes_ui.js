// Core module node UI definitions
// These define the frontend presentation of core nodes
//
// IMPORTANT: All nodes must be executable from the UI. There must never be
// a concept of a node that can't execute. The execute button always shows
// in the node editor (when not in read-only mode). Some nodes (like scheduled)
// may behave differently when executed manually vs triggered normally, but
// every node must support execution for UI testing/debugging purposes.

export const nodeTypes = [
    // Start node
    {
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
        execute: () => [{}],
    },

    // Scheduled node
    {
        id: 'scheduled',
        name: 'Scheduled',
        category: 'Input',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
        </svg>`,
        defaultData: { mode: 'interval', interval: 5, unit: 'minutes', cron: '*/5 * * * *' },
        getConnectors: () => ({
            inputs: [],
            outputs: [{ id: 'trigger', name: 'trigger' }],
        }),
        getProperties: (data) => [
            { id: 'mode', label: 'Mode', type: 'select', value: data.mode ?? 'interval', options: [
                { value: 'interval', label: 'Interval' },
                { value: 'cron', label: 'Cron Expression' },
            ]},
            // Interval mode properties
            ...(data.mode !== 'cron' ? [
                { id: 'interval', label: 'Interval', type: 'number', value: data.interval ?? 5, min: 1 },
                { id: 'unit', label: 'Unit', type: 'select', value: data.unit ?? 'minutes', options: [
                    { value: 'seconds', label: 'Seconds' },
                    { value: 'minutes', label: 'Minutes' },
                    { value: 'hours', label: 'Hours' },
                    { value: 'days', label: 'Days' },
                ]},
            ] : []),
            // Cron mode properties
            ...(data.mode === 'cron' ? [
                { id: 'cron', label: 'Cron Expression', type: 'text', value: data.cron ?? '*/5 * * * *',
                  placeholder: '*/5 * * * *',
                  instructions: 'Format: minute hour day month weekday (e.g., "0 9 * * 1-5" for 9am weekdays)' },
            ] : []),
        ],
        execute: (nodeData, inputs) => {
            return [{ time: new Date().toISOString() }];
        },
    },

    // Hardwired node
    {
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
        execute: (nodeData) => {
            try {
                return JSON.parse(nodeData.json || '[]');
            } catch (e) {
                return [{ error: 'Invalid JSON', message: e.message }];
            }
        },
    },

    // Set node
    {
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
    },

    // Transform node
    {
        id: 'transform',
        name: 'Transform',
        category: 'Transform',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>`,
        defaultData: { expression: '' },
        getConnectors: () => ({
            inputs: [{ id: 'data', name: 'data' }],
            outputs: [{ id: 'result', name: 'result' }],
        }),
        getProperties: (data) => [
            { id: 'expression', label: 'Expression', type: 'text', value: data.expression ?? '', placeholder: 'e.g. item.name.toUpperCase()' },
        ],
    },

    // IF node
    {
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
    },

    // HTTP node
    {
        id: 'http',
        name: 'HTTP',
        category: 'Action',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
        </svg>`,
        defaultData: { url: '', method: 'GET', headers: [], body_mode: 'none', json_body: '', body_fields: [], timeout: 30 },
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
                { value: 'HEAD', label: 'HEAD' },
                { value: 'OPTIONS', label: 'OPTIONS' },
            ]},
            { id: 'url', label: 'URL', type: 'text', value: data.url ?? '', placeholder: 'https://api.example.com/endpoint',
              instructions: 'Use {{ $.field }} to reference input data' },
            { id: 'headers', label: 'Headers', type: 'fieldlist', value: data.headers ?? [],
              instructions: 'Add custom headers (e.g., Authorization, Accept)' },
            { id: 'body_mode', label: 'Body', type: 'select', value: data.body_mode ?? 'none', options: [
                { value: 'none', label: 'None' },
                { value: 'json', label: 'Raw JSON' },
                { value: 'fields', label: 'Key-Value Fields' },
            ]},
            // JSON body textarea (shown when body_mode is 'json')
            ...(data.body_mode === 'json' ? [
                { id: 'json_body', label: 'JSON Body', type: 'textarea', value: data.json_body ?? '',
                  placeholder: '{"key": "value"}',
                  instructions: 'Raw JSON body. Use {{ $.field }} for dynamic values.' },
            ] : []),
            // Body fields (shown when body_mode is 'fields')
            ...(data.body_mode === 'fields' ? [
                { id: 'body_fields', label: 'Body Fields', type: 'fieldlist', value: data.body_fields ?? [],
                  instructions: 'Fields are sent as JSON. Values can use {{ $.field }} syntax.' },
            ] : []),
            { id: 'timeout', label: 'Timeout (seconds)', type: 'number', value: data.timeout ?? 30, min: 1, max: 300 },
        ],
    },

    // RSS node
    {
        id: 'rss',
        name: 'RSS',
        category: 'Input',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="6" cy="18" r="3"/>
            <path d="M6 6a12 12 0 0 1 12 12"/>
            <path d="M6 12a6 6 0 0 1 6 6"/>
        </svg>`,
        defaultData: { url: '' },
        getConnectors: () => ({
            inputs: [],
            outputs: [{ id: 'items', name: 'items' }],
        }),
        getProperties: (data) => [
            { id: 'url', label: 'Feed URL', type: 'text', value: data.url ?? '', placeholder: 'https://example.com/feed.xml' },
        ],
    },

    // Append to File node
    {
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
        kind: 'array',
    },
];
