// Node type registry - dynamically loads all node types from this directory
// To add a new node type, create a new file in this directory and import it here

import start from './start.js';
import scheduled from './scheduled.js';
import hardwired from './hardwired.js';
import rss from './rss.js';
import ifNode from './if.js';
import http from './http.js';
import transform from './transform.js';
import set from './set.js';
import appendToFile from './append_to_file.js';

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

// Build the node type definitions object from all imported nodes
const nodeTypes = [start, scheduled, hardwired, rss, ifNode, http, transform, set, appendToFile];

const nodeTypeDefinitions = {};
for (const nodeType of nodeTypes) {
    nodeTypeDefinitions[nodeType.id] = normalizeNodeType(nodeType);
}

export { nodeTypeDefinitions };

// Group node types by category
export function getNodeTypesByCategory() {
    const grouped = {};
    for (const nt of Object.values(nodeTypeDefinitions)) {
        if (!grouped[nt.category]) {
            grouped[nt.category] = [];
        }
        grouped[nt.category].push(nt);
    }
    return grouped;
}
