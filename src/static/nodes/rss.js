export default {
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
};
