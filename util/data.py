from dataclasses import dataclass
from mcp.types import CallToolResult

@dataclass
class AssistantResponseChunk:
    type: str
    content: str | dict 

@dataclass
class ToolCallInfo:
    id: str
    name: str
    args: dict
    result: CallToolResult