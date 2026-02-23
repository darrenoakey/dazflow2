// Docket module node UI definitions
// Provides nodes for interacting with the local Docket task manager.

const _docketIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
    <rect x="9" y="3" width="6" height="4" rx="1"/>
    <line x1="9" y1="12" x2="15" y2="12"/>
    <line x1="9" y1="16" x2="13" y2="16"/>
</svg>`;

const _seekIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="11" cy="11" r="8"/>
    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
    <path d="M8 11h6M11 8v6"/>
</svg>`;

const _statusOptions = [
    { value: 'new', label: 'New' },
    { value: 'reviewing', label: 'Reviewing' },
    { value: 'interested', label: 'Interested' },
    { value: 'applied', label: 'Applied' },
    { value: 'interviewing', label: 'Interviewing' },
    { value: 'offer', label: 'Offer' },
    { value: 'rejected', label: 'Rejected' },
    { value: 'archived', label: 'Archived' },
];

const _statusOptionsWithEmpty = [
    { value: '', label: 'All statuses' },
    ..._statusOptions,
];

export const nodeTypes = [
    // =========================================================================
    // CREATE TASK
    // =========================================================================
    {
        id: 'docket_create_task',
        name: 'Create Task',
        category: 'Docket',
        kind: 'map',
        icon: _docketIcon,
        defaultData: {
            title: '',
            description: '',
            url: '',
            company: '',
            location: '',
            salary: '',
            tags: '',
            status: 'new',
            source: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'task' }],
        }),
        getProperties: (data) => [
            {
                id: 'title',
                label: 'Title',
                type: 'expression',
                value: data.title ?? '',
                placeholder: 'Task title',
                instructions: 'Title of the task. Supports expressions.',
            },
            {
                id: 'description',
                label: 'Description',
                type: 'textarea',
                value: data.description ?? '',
                placeholder: 'Task description or notes...',
            },
            {
                id: 'company',
                label: 'Company',
                type: 'expression',
                value: data.company ?? '',
                placeholder: 'Company name',
            },
            {
                id: 'location',
                label: 'Location',
                type: 'expression',
                value: data.location ?? '',
                placeholder: 'City, State',
            },
            {
                id: 'salary',
                label: 'Salary',
                type: 'expression',
                value: data.salary ?? '',
                placeholder: '$80k-$100k',
            },
            {
                id: 'url',
                label: 'URL',
                type: 'expression',
                value: data.url ?? '',
                placeholder: 'https://...',
            },
            {
                id: 'status',
                label: 'Status',
                type: 'select',
                value: data.status ?? 'new',
                options: _statusOptions,
            },
            {
                id: 'tags',
                label: 'Tags',
                type: 'text',
                value: data.tags ?? '',
                placeholder: 'tag1, tag2, tag3',
                instructions: 'Comma-separated list of tags',
            },
            {
                id: 'source',
                label: 'Source',
                type: 'text',
                value: data.source ?? '',
                placeholder: 'seek-email',
                instructions: 'Where this task came from',
            },
        ],
    },

    // =========================================================================
    // UPDATE STATUS
    // =========================================================================
    {
        id: 'docket_update_status',
        name: 'Update Task Status',
        category: 'Docket',
        kind: 'map',
        icon: _docketIcon,
        defaultData: {
            task_id: '',
            status: 'reviewing',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'task' }],
        }),
        getProperties: (data) => [
            {
                id: 'task_id',
                label: 'Task ID',
                type: 'expression',
                value: data.task_id ?? '',
                placeholder: '{{$.previous_node.id}}',
                instructions: 'ID of the task to update',
            },
            {
                id: 'status',
                label: 'New Status',
                type: 'select',
                value: data.status ?? 'reviewing',
                options: _statusOptions,
            },
        ],
    },

    // =========================================================================
    // LIST TASKS
    // =========================================================================
    {
        id: 'docket_list_tasks',
        name: 'List Tasks',
        category: 'Docket',
        kind: 'array',
        icon: _docketIcon,
        defaultData: {
            status: '',
            search: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'tasks' }],
        }),
        getProperties: (data) => [
            {
                id: 'status',
                label: 'Filter by Status',
                type: 'select',
                value: data.status ?? '',
                options: _statusOptionsWithEmpty,
            },
            {
                id: 'search',
                label: 'Search',
                type: 'text',
                value: data.search ?? '',
                placeholder: 'Search title, company...',
            },
        ],
    },

    // =========================================================================
    // GET TASK
    // =========================================================================
    {
        id: 'docket_get_task',
        name: 'Get Task',
        category: 'Docket',
        kind: 'map',
        icon: _docketIcon,
        defaultData: {
            task_id: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'input' }],
            outputs: [{ id: 'output', name: 'task' }],
        }),
        getProperties: (data) => [
            {
                id: 'task_id',
                label: 'Task ID',
                type: 'expression',
                value: data.task_id ?? '',
                placeholder: '{{$.previous_node.id}}',
                instructions: 'ID of the task to retrieve',
            },
        ],
    },

    // =========================================================================
    // PARSE SEEK EMAIL
    // =========================================================================
    {
        id: 'docket_parse_seek_email',
        name: 'Parse SEEK Email',
        category: 'Docket',
        kind: 'array',
        icon: _seekIcon,
        defaultData: {},
        getConnectors: () => ({
            inputs: [{ id: 'input', name: 'email' }],
            outputs: [{ id: 'output', name: 'tasks' }],
        }),
        getProperties: (_data) => [
            {
                id: '_info',
                label: 'Info',
                type: 'text',
                value: '',
                placeholder: '',
                instructions: 'Receives an email object (from Get Email node). Uses Claude Haiku to extract individual job listings from the HTML body and creates a Docket task for each one. Returns the list of created tasks.',
                readonly: true,
            },
        ],
    },
];
