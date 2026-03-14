"""
flowscript-ldp: LDP Mode 3 (Semantic Graphs) reference implementation.

First implementation of Mode 3 from the LLM Delegate Protocol (arXiv:2603.08852).
Uses FlowScript IR as the payload format for structured relationship representations.
"""

__version__ = "0.2.0"

from .ir import (
    IR,
    Node,
    NodeType,
    Relationship,
    RelationType,
    State,
    StateType,
    Provenance,
    SourceSpan,
    GraphInvariants,
    Author,
    StateFields,
    IRMetadata,
)
from .parser_bridge import ParserBridge, ParserError
from .query import QueryEngine
from .payload import FlowScriptPayload
from .fallback import FallbackChain
from .adapter import FlowScriptMode3Adapter, get_jamjet_tools

__all__ = [
    "IR",
    "Node",
    "NodeType",
    "Relationship",
    "RelationType",
    "State",
    "StateType",
    "Provenance",
    "SourceSpan",
    "GraphInvariants",
    "Author",
    "StateFields",
    "IRMetadata",
    "ParserBridge",
    "ParserError",
    "QueryEngine",
    "FlowScriptPayload",
    "FallbackChain",
    "FlowScriptMode3Adapter",
    "get_jamjet_tools",
]

# Optional integrations — only available when deps are installed
try:
    from .delegate import FlowScriptMode3Delegate
    __all__.append("FlowScriptMode3Delegate")
except ImportError:
    pass

try:
    from .adapter import FlowScriptLdpAdapter
    __all__.append("FlowScriptLdpAdapter")
except ImportError:
    pass
