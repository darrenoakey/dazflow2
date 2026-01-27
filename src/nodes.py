"""
Node type definitions for dazflow2.
This module now delegates to the module loader for all node types.
"""

from .module_loader import get_all_node_types, get_node_type

# Re-export for backwards compatibility
NODE_TYPES = get_all_node_types()

__all__ = ["NODE_TYPES", "get_node_type"]
