// Node type registry - dynamically loads all node types from modules
// To add a new node type, create a module in the modules/ directory

// Cached node type definitions
let nodeTypeDefinitions = {};
let loadPromise = null;

// Wrap map nodes to be array nodes
// Map nodes define execute(nodeData, item) -> item
// This wraps them to execute(nodeData, inputs) -> outputs (array in, array out)
// Also evaluates {{expressions}} in nodeData per-item using window.evaluateDataExpressions if available
function normalizeNodeType(nodeType) {
    if (nodeType.kind !== 'map' || !nodeType.execute) return nodeType;

    const itemExecute = nodeType.execute;
    return {
        ...nodeType,
        execute: (nodeData, inputs) => {
            // Normalize inputs to array; empty/missing inputs treated as single empty item
            let inputArray = Array.isArray(inputs) ? inputs : [inputs];
            if (inputArray.length === 0) {
                inputArray = [{}];
            }
            return inputArray.map(item => {
                // Evaluate expressions in nodeData for this item
                // The $ in expressions refers to the current item
                const evaluator = window.evaluateDataExpressions;
                const evaluatedData = evaluator ? evaluator(nodeData, item) : nodeData;
                return itemExecute(evaluatedData, item);
            });
        }
    };
}

// Load all modules from the server
async function loadModules() {
    if (loadPromise) return loadPromise;

    loadPromise = (async () => {
        try {
            // Fetch module info from the API
            const response = await fetch('/api/modules');
            const data = await response.json();

            // Dynamically import each module's UI file
            for (const path of data.moduleUIPaths) {
                try {
                    const module = await import(path);
                    if (module.nodeTypes) {
                        for (const nodeType of module.nodeTypes) {
                            nodeTypeDefinitions[nodeType.id] = normalizeNodeType(nodeType);
                        }
                    }
                } catch (e) {
                    console.warn(`Failed to load module from ${path}:`, e);
                }
            }

            return { nodeTypes: data.nodeTypes, credentialTypes: data.credentialTypes };
        } catch (e) {
            console.error('Failed to load modules:', e);
            return { nodeTypes: [], credentialTypes: [] };
        }
    })();

    return loadPromise;
}

// Get node type definitions (must call loadModules first)
function getNodeTypeDefinitions() {
    return nodeTypeDefinitions;
}

// Group node types by category
function getNodeTypesByCategory() {
    const grouped = {};
    for (const nt of Object.values(nodeTypeDefinitions)) {
        if (!grouped[nt.category]) {
            grouped[nt.category] = [];
        }
        grouped[nt.category].push(nt);
    }
    return grouped;
}

export { nodeTypeDefinitions, getNodeTypesByCategory, loadModules, getNodeTypeDefinitions };
