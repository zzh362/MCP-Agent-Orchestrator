from util.constants import SERVER_CONFIG_FILE
from util.data import ToolCallInfo

import json
import logging
from rich import logging as rich_logging
from contextlib import AsyncExitStack


from mcp import ClientSession, StdioServerParameters, Tool
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(rich_logging.RichHandler())


class MCPClient:
    def __init__(self):
        # 所有连接成功的 MCP Server sessions
        self.mcpSessions = {}     
        # 所有 Server中的所有工具集合
        self.tools: list[Tool] = []
        # 工具名与 工具所在session的映射关系
        self.mcpToolsSessionMap = {}
        self.exit_stack = AsyncExitStack()
        # Server配置文件
        self.mcpServersConfig = {}
    
    
    async def initialize(self, config_file=SERVER_CONFIG_FILE):
        with open(config_file, "r") as f:
            self.mcpServersConfig = json.load(f)
        await self.connect_to_server(self.mcpServersConfig)

    async def connect_to_server(self, configs: dict):
        """
        Example configs input:
        {
            "weather": {
                "command": "python",
                "args": [
                "./server/weather.py"
                ]
            },
            "other_server": {...}
        }
        """
        for server_name, config in configs.items():
            server_params = StdioServerParameters(**config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            stdio, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(stdio, write)
            )

            await session.initialize()

            # List available tools
            response = await session.list_tools()
            tools = response.tools
            logger.info(
                f"\nConnected to server with tools: {[tool.name for tool in tools]}"
            )

            self.mcpSessions[server_name] = session
            for tool in tools:
                self.mcpToolsSessionMap[tool.name] = session

            self.tools.extend(tools)
    
        
    async def call_tool(self, id, tool_name, tool_args) -> ToolCallInfo:
        logger.debug(f"call_tool: {tool_name} with args {str(tool_args)[:100]}...")
        session: ClientSession = self.mcpToolsSessionMap[tool_name]
        if session is None:
            return ToolCallInfo(
                id=id,
                name=tool_name,
                args=tool_args,
                result=CallToolResult(
                    content=[{"text": f"Cannot find servers for tool {tool_name}"}],
                    isError=True,
                ),
            )

        result = await session.call_tool(tool_name, tool_args)
        logger.debug(
            f"[Calling tool {tool_name} with args {tool_args}], \n  result: {
                result.content}"
        )
        return ToolCallInfo(id=id, name=tool_name, args=tool_args, result=result)
    

    def list_tools(self):
        return self.tools

    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()
