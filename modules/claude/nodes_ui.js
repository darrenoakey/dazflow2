// Claude module node UI definitions

export const nodeTypes = [
    {
        id: 'claude_agent',
        name: 'Claude Agent',
        category: 'AI',
        kind: 'map',
        icon: `<svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
        </svg>`,
        defaultData: {
            prompt: '',
            conversation_id: '',
            model: '',
            allowed_tools: 'Read, Write, Edit, Bash, Glob, Grep',
            system_prompt: '',
            permission_mode: 'acceptEdits',
            cwd: '',
        },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'response', name: 'response' }],
        }),
        getProperties: (data) => [
            {
                id: 'prompt',
                label: 'Prompt',
                type: 'textarea',
                value: data.prompt ?? '',
                placeholder: 'Enter the prompt for the Claude agent...',
                instructions: 'The prompt to send to Claude. Use {{$.field}} to include data from previous nodes.',
            },
            {
                id: 'conversation_id',
                label: 'Conversation ID',
                type: 'text',
                value: data.conversation_id ?? '',
                placeholder: 'Optional: my-conversation-123',
                instructions: 'Optional. If provided, continues a previous conversation. Multiple calls with the same ID will share context.',
            },
            {
                id: 'model',
                label: 'Model',
                type: 'select',
                value: data.model ?? '',
                options: [
                    { value: '', label: 'Default' },
                    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
                    { value: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
                    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5' },
                ],
            },
            {
                id: 'allowed_tools',
                label: 'Allowed Tools',
                type: 'text',
                value: data.allowed_tools ?? 'Read, Write, Edit, Bash, Glob, Grep',
                placeholder: 'Read, Write, Edit, Bash',
                instructions: 'Comma-separated list of tools the agent can use.',
            },
            {
                id: 'system_prompt',
                label: 'System Prompt',
                type: 'textarea',
                value: data.system_prompt ?? '',
                placeholder: 'Optional custom system prompt...',
                instructions: 'Optional. Custom system prompt to use instead of the default.',
            },
            {
                id: 'permission_mode',
                label: 'Permission Mode',
                type: 'select',
                value: data.permission_mode ?? 'acceptEdits',
                options: [
                    { value: 'acceptEdits', label: 'Accept Edits (auto-approve file changes)' },
                    { value: 'default', label: 'Default (prompt for permissions)' },
                    { value: 'bypassPermissions', label: 'Bypass All (use with caution)' },
                    { value: 'plan', label: 'Plan Mode (no execution)' },
                ],
            },
            {
                id: 'cwd',
                label: 'Working Directory',
                type: 'directory_path',
                value: data.cwd ?? '',
                placeholder: '/path/to/project',
                instructions: 'Optional. The working directory for the agent.',
            },
        ],
    },
    {
        id: 'claude_json',
        name: 'Claude JSON',
        category: 'AI',
        kind: 'array',
        icon: `<svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h-2v-2h2v2zm0-4h-2V7h2v6zm4 4h-2v-2h2v2zm0-4h-2V7h2v6z"/>
        </svg>`,
        defaultData: {
            prompt: '',
            model: 'claude-haiku-4-5-20251001',
            max_tokens: 4096,
        },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'result', name: 'result' }],
        }),
        getProperties: (data) => [
            {
                id: 'prompt',
                label: 'Prompt',
                type: 'textarea',
                value: data.prompt ?? '',
                placeholder: 'Extract structured data as JSON...',
                instructions: 'Prompt for Claude. Use {{$.field}} for input data. Response must be valid JSON.',
            },
            {
                id: 'model',
                label: 'Model',
                type: 'select',
                value: data.model ?? 'claude-haiku-4-5-20251001',
                options: [
                    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (fast, cheap)' },
                    { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6' },
                    { value: 'claude-opus-4-6', label: 'Claude Opus 4.6' },
                ],
            },
            {
                id: 'max_tokens',
                label: 'Max Tokens',
                type: 'number',
                value: data.max_tokens ?? 4096,
                min: 1,
                max: 65536,
                instructions: 'Maximum tokens in Claude response.',
            },
        ],
    },
];
