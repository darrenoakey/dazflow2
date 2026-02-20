// Agent Link module node UI definitions
// Provides triggers and actions for all agent-link service categories.
// All nodes appear in the "Agent Link" category (collapsed by default).

const _mailIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
    <polyline points="22,6 12,13 2,6"/>
</svg>`;

const _calendarIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
    <line x1="16" y1="2" x2="16" y2="6"/>
    <line x1="8" y1="2" x2="8" y2="6"/>
    <line x1="3" y1="10" x2="21" y2="10"/>
</svg>`;

const _contactIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
</svg>`;

const _taskIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <polyline points="9 11 12 14 22 4"/>
    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
</svg>`;

const _linkIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
</svg>`;

const _sourceField = (data) => ({
    id: 'source',
    label: 'Source',
    type: 'text',
    value: data.source ?? '',
    placeholder: 'gmail-user@example.com (leave empty for all)',
    instructions: 'Filter by agent-link source name. Leave empty to use all connected sources.',
});

export const nodeTypes = [
    // =========================================================================
    // EMAIL TRIGGER
    // =========================================================================
    {
        id: 'email_trigger',
        name: 'Email Received',
        category: 'Agent Link',
        kind: 'array',
        icon: _mailIcon,
        defaultData: {
            from_filter: '',
            subject_filter: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [],
            outputs: [{ id: 'email', name: 'email' }],
        }),
        getProperties: (data) => [
            {
                id: 'from_filter',
                label: 'From Filter',
                type: 'text',
                value: data.from_filter ?? '',
                placeholder: 'noreply@example.com',
                instructions: 'Only trigger for emails from this address. Partial match, case-insensitive. Leave empty for all senders.',
            },
            {
                id: 'subject_filter',
                label: 'Subject Filter',
                type: 'text',
                value: data.subject_filter ?? '',
                placeholder: 'Invoice',
                instructions: 'Only trigger for emails with this in the subject. Partial match, case-insensitive. Leave empty for all subjects.',
            },
            _sourceField(data),
        ],
    },

    // =========================================================================
    // MAIL ACTIONS
    // =========================================================================
    {
        id: 'email_list',
        name: 'List Emails',
        category: 'Agent Link',
        kind: 'array',
        icon: _mailIcon,
        defaultData: {
            folder: 'INBOX',
            query: '',
            max_results: 10,
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'folder',
                label: 'Folder',
                type: 'text',
                value: data.folder ?? 'INBOX',
                placeholder: 'INBOX',
            },
            {
                id: 'query',
                label: 'Query',
                type: 'text',
                value: data.query ?? '',
                placeholder: 'is:unread from:boss@company.com',
                instructions: 'Optional filter query (Gmail search syntax)',
            },
            {
                id: 'max_results',
                label: 'Max Results',
                type: 'number',
                value: data.max_results ?? 10,
                min: 1,
                max: 100,
            },
            _sourceField(data),
        ],
    },
    {
        id: 'email_search',
        name: 'Search Emails',
        category: 'Agent Link',
        kind: 'array',
        icon: _mailIcon,
        defaultData: {
            query: '',
            max_results: 10,
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'query',
                label: 'Search Query',
                type: 'text',
                value: data.query ?? '',
                placeholder: 'from:notifications@github.com is:unread',
                instructions: 'Gmail search query syntax',
            },
            {
                id: 'max_results',
                label: 'Max Results',
                type: 'number',
                value: data.max_results ?? 10,
                min: 1,
                max: 100,
            },
            _sourceField(data),
        ],
    },
    {
        id: 'email_get',
        name: 'Get Email',
        category: 'Agent Link',
        kind: 'map',
        icon: _mailIcon,
        defaultData: {
            id: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'id',
                label: 'Email ID',
                type: 'text',
                value: data.id ?? '',
                placeholder: '{{ $.email_list.messages[0].id }}',
                instructions: 'The email ID to fetch. Returns full body.',
            },
            _sourceField(data),
        ],
    },
    {
        id: 'email_send',
        name: 'Send Email',
        category: 'Agent Link',
        kind: 'map',
        icon: _mailIcon,
        defaultData: {
            to: '',
            subject: '',
            body: '',
            cc: '',
            bcc: '',
            html: false,
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'to',
                label: 'To',
                type: 'text',
                value: data.to ?? '',
                placeholder: 'recipient@example.com',
            },
            {
                id: 'subject',
                label: 'Subject',
                type: 'text',
                value: data.subject ?? '',
                placeholder: 'Hello from dazflow!',
            },
            {
                id: 'body',
                label: 'Body',
                type: 'textarea',
                value: data.body ?? '',
                placeholder: 'Email body text...',
                instructions: 'Use {{ $.field }} to reference input data',
            },
            {
                id: 'cc',
                label: 'CC',
                type: 'text',
                value: data.cc ?? '',
                placeholder: 'cc@example.com (optional)',
            },
            {
                id: 'bcc',
                label: 'BCC',
                type: 'text',
                value: data.bcc ?? '',
                placeholder: 'bcc@example.com (optional)',
            },
            {
                id: 'html',
                label: 'HTML Body',
                type: 'checkbox',
                value: data.html ?? false,
                instructions: 'Enable if body contains HTML markup',
            },
            _sourceField(data),
        ],
    },
    {
        id: 'email_move',
        name: 'Move Email',
        category: 'Agent Link',
        kind: 'map',
        icon: _mailIcon,
        defaultData: {
            id: '',
            folder: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'id',
                label: 'Email ID',
                type: 'text',
                value: data.id ?? '',
                placeholder: '{{ $.email.id }}',
            },
            {
                id: 'folder',
                label: 'Destination Folder',
                type: 'text',
                value: data.folder ?? '',
                placeholder: 'Archive',
            },
            _sourceField(data),
        ],
    },
    {
        id: 'email_mark_read',
        name: 'Mark Email Read',
        category: 'Agent Link',
        kind: 'map',
        icon: _mailIcon,
        defaultData: {
            id: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'id',
                label: 'Email ID',
                type: 'text',
                value: data.id ?? '',
                placeholder: '{{ $.email.id }}',
            },
            _sourceField(data),
        ],
    },
    {
        id: 'email_delete',
        name: 'Delete Email',
        category: 'Agent Link',
        kind: 'map',
        icon: _mailIcon,
        defaultData: {
            id: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'id',
                label: 'Email ID',
                type: 'text',
                value: data.id ?? '',
                placeholder: '{{ $.email.id }}',
            },
            _sourceField(data),
        ],
    },
    {
        id: 'email_list_folders',
        name: 'List Email Folders',
        category: 'Agent Link',
        kind: 'array',
        icon: _mailIcon,
        defaultData: {
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            _sourceField(data),
        ],
    },

    // =========================================================================
    // CALENDAR ACTIONS
    // =========================================================================
    {
        id: 'calendar_list',
        name: 'List Calendars',
        category: 'Agent Link',
        kind: 'array',
        icon: _calendarIcon,
        defaultData: {
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            _sourceField(data),
        ],
    },
    {
        id: 'calendar_list_events',
        name: 'List Calendar Events',
        category: 'Agent Link',
        kind: 'array',
        icon: _calendarIcon,
        defaultData: {
            calendar_id: 'primary',
            time_min: '',
            time_max: '',
            max_results: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'calendar_id',
                label: 'Calendar ID',
                type: 'text',
                value: data.calendar_id ?? 'primary',
                placeholder: 'primary',
                instructions: 'Use "primary" for the main calendar, or get IDs from List Calendars',
            },
            {
                id: 'time_min',
                label: 'From (RFC3339)',
                type: 'text',
                value: data.time_min ?? '',
                placeholder: '2026-02-20T00:00:00Z',
                instructions: 'Start of time range (optional)',
            },
            {
                id: 'time_max',
                label: 'To (RFC3339)',
                type: 'text',
                value: data.time_max ?? '',
                placeholder: '2026-02-27T23:59:59Z',
                instructions: 'End of time range (optional)',
            },
            {
                id: 'max_results',
                label: 'Max Results',
                type: 'number',
                value: data.max_results ?? '',
                min: 1,
                max: 2500,
                placeholder: '250',
            },
            _sourceField(data),
        ],
    },
    {
        id: 'calendar_create_event',
        name: 'Create Calendar Event',
        category: 'Agent Link',
        kind: 'map',
        icon: _calendarIcon,
        defaultData: {
            calendar_id: 'primary',
            summary: '',
            start: '',
            end: '',
            description: '',
            location: '',
            attendees: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'calendar_id',
                label: 'Calendar ID',
                type: 'text',
                value: data.calendar_id ?? 'primary',
                placeholder: 'primary',
            },
            {
                id: 'summary',
                label: 'Title',
                type: 'text',
                value: data.summary ?? '',
                placeholder: 'Team Meeting',
            },
            {
                id: 'start',
                label: 'Start (RFC3339)',
                type: 'text',
                value: data.start ?? '',
                placeholder: '2026-02-25T10:00:00+11:00',
            },
            {
                id: 'end',
                label: 'End (RFC3339)',
                type: 'text',
                value: data.end ?? '',
                placeholder: '2026-02-25T11:00:00+11:00',
            },
            {
                id: 'description',
                label: 'Description',
                type: 'textarea',
                value: data.description ?? '',
                placeholder: 'Event details...',
            },
            {
                id: 'location',
                label: 'Location',
                type: 'text',
                value: data.location ?? '',
                placeholder: 'Conference Room A',
            },
            {
                id: 'attendees',
                label: 'Attendees',
                type: 'text',
                value: data.attendees ?? '',
                placeholder: 'person@example.com, other@example.com',
                instructions: 'Comma-separated email addresses',
            },
            _sourceField(data),
        ],
    },

    // =========================================================================
    // CONTACTS ACTIONS
    // =========================================================================
    {
        id: 'contacts_list',
        name: 'List Contacts',
        category: 'Agent Link',
        kind: 'array',
        icon: _contactIcon,
        defaultData: {
            query: '',
            max_results: 100,
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'query',
                label: 'Search Query',
                type: 'text',
                value: data.query ?? '',
                placeholder: 'John',
                instructions: 'Optional search query to filter contacts',
            },
            {
                id: 'max_results',
                label: 'Max Results',
                type: 'number',
                value: data.max_results ?? 100,
                min: 1,
                max: 1000,
            },
            _sourceField(data),
        ],
    },

    // =========================================================================
    // TASKS ACTIONS
    // =========================================================================
    {
        id: 'tasks_list_lists',
        name: 'List Task Lists',
        category: 'Agent Link',
        kind: 'array',
        icon: _taskIcon,
        defaultData: {
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            _sourceField(data),
        ],
    },
    {
        id: 'tasks_list',
        name: 'List Tasks',
        category: 'Agent Link',
        kind: 'array',
        icon: _taskIcon,
        defaultData: {
            list_id: '',
            status_filter: 'all',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'list_id',
                label: 'Task List ID',
                type: 'text',
                value: data.list_id ?? '',
                placeholder: 'MDc4OTc4NjE4ODY5NjM5OTU1NzE6MDow',
                instructions: 'Optional. Leave empty for default list. Get IDs from List Task Lists.',
            },
            {
                id: 'status_filter',
                label: 'Status',
                type: 'select',
                value: data.status_filter ?? 'all',
                options: [
                    { value: 'all', label: 'All' },
                    { value: 'needsAction', label: 'Needs Action' },
                    { value: 'completed', label: 'Completed' },
                ],
            },
            _sourceField(data),
        ],
    },
    {
        id: 'tasks_create',
        name: 'Create Task',
        category: 'Agent Link',
        kind: 'map',
        icon: _taskIcon,
        defaultData: {
            list_id: '',
            title: '',
            notes: '',
            due_date: '',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'list_id',
                label: 'Task List ID',
                type: 'text',
                value: data.list_id ?? '',
                placeholder: 'MDc4...',
                instructions: 'Optional. Leave empty for default list.',
            },
            {
                id: 'title',
                label: 'Title',
                type: 'text',
                value: data.title ?? '',
                placeholder: 'Buy milk',
            },
            {
                id: 'notes',
                label: 'Notes',
                type: 'textarea',
                value: data.notes ?? '',
                placeholder: 'Optional notes...',
            },
            {
                id: 'due_date',
                label: 'Due Date (ISO 8601)',
                type: 'text',
                value: data.due_date ?? '',
                placeholder: '2026-02-25',
                instructions: 'Optional due date in YYYY-MM-DD format',
            },
            _sourceField(data),
        ],
    },

    // =========================================================================
    // GENERIC AGENT LINK CALL
    // =========================================================================
    {
        id: 'agent_link_call',
        name: 'Agent Link Call',
        category: 'Agent Link',
        kind: 'array',
        icon: _linkIcon,
        defaultData: {
            category: '',
            function: '',
            params: '{}',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'output' }],
        }),
        getProperties: (data) => [
            {
                id: 'category',
                label: 'Category',
                type: 'text',
                value: data.category ?? '',
                placeholder: 'mail',
                instructions: 'Service category: mail, calendar, contacts, tasks, search, llm, messaging, etc.',
            },
            {
                id: 'function',
                label: 'Function',
                type: 'text',
                value: data.function ?? '',
                placeholder: 'list-messages',
                instructions: 'Function name within the category',
            },
            {
                id: 'params',
                label: 'Parameters (JSON)',
                type: 'textarea',
                value: data.params ?? '{}',
                placeholder: '{"folder": "INBOX", "max_results": 10}',
                instructions: 'JSON object with function parameters',
            },
            _sourceField(data),
        ],
    },
];
