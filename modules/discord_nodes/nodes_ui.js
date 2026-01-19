// Discord module node UI definitions

export const nodeTypes = [
    {
        id: 'discord_trigger',
        name: 'Trigger',
        category: 'Discord',
        kind: 'array',
        requiredCredential: 'discord',
        icon: `<svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026 13.83 13.83 0 0 0 1.226-1.963.074.074 0 0 0-.041-.104 13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028zM8.02 15.278c-1.182 0-2.157-1.069-2.157-2.38 0-1.312.956-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.956 2.38-2.157 2.38zm7.975 0c-1.183 0-2.157-1.069-2.157-2.38 0-1.312.955-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.946 2.38-2.157 2.38z"/>
        </svg>`,
        defaultData: { server_id: '', channel_id: '', mode: 'new_messages' },
        getConnectors: () => ({
            inputs: [],  // Trigger nodes have no inputs
            outputs: [{ id: 'message', name: 'message' }],
        }),
        getProperties: (data) => [
            {
                id: 'server_id',
                label: 'Server',
                type: 'dynamicSelect',
                value: data.server_id ?? '',
                enumKey: 'server_id',  // Key for the dynamicEnums function
            },
            {
                id: 'channel_id',
                label: 'Channel',
                type: 'dynamicSelect',
                value: data.channel_id ?? '',
                enumKey: 'channel_id',
                dependsOn: ['server_id'],  // Depends on server_id being set
            },
            {
                id: 'mode',
                label: 'Trigger On',
                type: 'select',
                value: data.mode ?? 'new_messages',
                options: [
                    { value: 'new_messages', label: 'New Messages' },
                    { value: 'replies', label: 'Replies Only' },
                    { value: 'new_messages_and_replies', label: 'New Messages & Replies' },
                ],
            },
        ],
    },
    {
        id: 'discord_send',
        name: 'Send Message',
        category: 'Discord',
        kind: 'array',
        requiredCredential: 'discord',
        icon: `<svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M20.317 4.492c-1.53-.69-3.17-1.2-4.885-1.49a.075.075 0 0 0-.079.036c-.21.369-.444.85-.608 1.23a18.566 18.566 0 0 0-5.487 0 12.36 12.36 0 0 0-.617-1.23A.077.077 0 0 0 8.562 3c-1.714.29-3.354.8-4.885 1.491a.07.07 0 0 0-.032.027C.533 9.093-.32 13.555.099 17.961a.08.08 0 0 0 .031.055 20.03 20.03 0 0 0 5.993 2.98.078.078 0 0 0 .084-.026 13.83 13.83 0 0 0 1.226-1.963.074.074 0 0 0-.041-.104 13.201 13.201 0 0 1-1.872-.878.075.075 0 0 1-.008-.125c.126-.093.252-.19.372-.287a.075.075 0 0 1 .078-.01c3.927 1.764 8.18 1.764 12.061 0a.075.075 0 0 1 .079.009c.12.098.245.195.372.288a.075.075 0 0 1-.006.125c-.598.344-1.22.635-1.873.877a.075.075 0 0 0-.041.105c.36.687.772 1.341 1.225 1.962a.077.077 0 0 0 .084.028 19.963 19.963 0 0 0 6.002-2.981.076.076 0 0 0 .032-.054c.5-5.094-.838-9.52-3.549-13.442a.06.06 0 0 0-.031-.028zM8.02 15.278c-1.182 0-2.157-1.069-2.157-2.38 0-1.312.956-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.956 2.38-2.157 2.38zm7.975 0c-1.183 0-2.157-1.069-2.157-2.38 0-1.312.955-2.38 2.157-2.38 1.21 0 2.176 1.077 2.157 2.38 0 1.312-.946 2.38-2.157 2.38z"/>
        </svg>`,
        defaultData: { server_id: '', channel_id: '', message: '', reply_to_id: '' },
        getConnectors: () => ({
            inputs: [{ id: 'trigger', name: 'trigger' }],
            outputs: [{ id: 'result', name: 'result' }],
        }),
        getProperties: (data) => [
            {
                id: 'server_id',
                label: 'Server',
                type: 'dynamicSelect',
                value: data.server_id ?? '',
                enumKey: 'server_id',
            },
            {
                id: 'channel_id',
                label: 'Channel',
                type: 'dynamicSelect',
                value: data.channel_id ?? '',
                enumKey: 'channel_id',
                dependsOn: ['server_id'],
            },
            {
                id: 'message',
                label: 'Message',
                type: 'textarea',
                value: data.message ?? '',
                instructions: 'Use {{ $.field }} to reference input data',
            },
            {
                id: 'reply_to_id',
                label: 'Reply To Message ID',
                type: 'text',
                value: data.reply_to_id ?? '',
                instructions: 'Optional: Leave blank to send as new message, or use {{ $.id }} to reply',
            },
        ],
    },
];
