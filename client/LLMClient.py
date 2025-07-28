from model.QwenModel import QwenModel
from .MCPClient import MCPClient
from util.data import AssistantResponseChunk, ToolCallInfo
from util.mytools import get_tools_format, is_valid_json
from mcp.types import CallToolResult

from typing import Any
import asyncio
import json

from openai import AsyncStream
from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import ChoiceDeltaToolCall

from mcp import Tool


class LLMClient:
    
    def __init__(self):
        # 传递给模型接口的工具列表
        self.available_tools = []
        # MCPClient支持的所有工具列表
        self.tools: list[Tool] = []  
        # MCPClient
        self.mcpClient = MCPClient()

        self.qwenClient = QwenModel()


    # async with中的初始化方法
    async def __aenter__(self):
        await self.mcpClient.initialize()
        self.tools = self.mcpClient.list_tools()
        self.available_tools = get_tools_format(self.tools, type="qwen")
        return self

    # 退出的方法
    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.mcpClient.cleanup()

    async def get_chat_completion(self, messages):
        return await self.qwenClient.get_chat_completion(messages, self.available_tools)
    
    def get_tool_result_message(
        self, result: CallToolResult | Any, tool_call_id: str, type="tool"
    ):
        if type == "tool":
            return {
                "content": (
                    result.content[0].text
                    if isinstance(result, CallToolResult)
                    else str(result)
                ),
                "role": "tool",
                "tool_call_id": tool_call_id,
            }
        if type == "user":
            return {"content": result.content, "role": "user", "name": "tool caller"}

    async def process_streamed_response(self, response: AsyncStream[ChatCompletionChunk]):
        async for chunk in response:
            delta = chunk.choices[0].delta
            if hasattr(delta, "reasoning_content") and delta.reasoning_content != None:
                yield AssistantResponseChunk(type="thinking", content=delta.reasoning_content)

            else:
                if delta.content is not None and delta.content != "":
                    yield AssistantResponseChunk(type="answer", content=delta.content)

                if delta.tool_calls is not None:
                    for tool_call in delta.tool_calls:
                        if (
                            tool_call.function
                            and not tool_call.function.name
                            and not tool_call.function.arguments
                        ):
                            break

                        yield AssistantResponseChunk(type="tool_call", content=tool_call)

    async def get_assistant_response(self, messages):

        while True:
            response = await self.get_chat_completion(messages)
            result = self.process_streamed_response(response)

            answer_content = ""
            reasoning_content = ""
            tool_call_message_params: dict[int:ChoiceDeltaToolCall] = {}
            tool_call_tasks = []
            tool_call_info = {}
            notified_calls = set()
            
            async for chunk in result:
                if chunk.type == "answer":
                    answer_content += chunk.content
                    yield chunk
                elif chunk.type == "thinking":
                    reasoning_content += chunk.content
                    yield chunk
                elif chunk.type == "tool_call":
                    tool_call_param: ChoiceDeltaToolCall = chunk.content
                    index = tool_call_param.index
                    if index not in tool_call_message_params:
                        tool_call_message_params[index] = tool_call_param
                    else:
                        tool_call_message_params[
                            index
                        ].function.arguments += tool_call_param.function.arguments

                    tool_call_param = tool_call_message_params[index]
                    if is_valid_json(tool_call_param.function.arguments):

                        tool_name = tool_call_param.function.name
                        tool_args = json.loads(tool_call_param.function.arguments)

                        # 创建工具调用的异步任务
                        task = asyncio.create_task(
                            self.mcpClient.call_tool(
                                tool_call_param.id, tool_name, tool_args
                            )
                        )
                        tool_call_tasks.append(task)

                        # 记录工具调用信息，id用来后续获取工具调用的结果
                        tool_info = ToolCallInfo(
                            id=tool_call_param.id,
                            name=tool_name,
                            args=tool_args,
                            result=None,
                        )
                        tool_call_info[tool_call_param.id] = tool_info

                        notified_calls.add(tool_call_param.id)
                        
                        # 将当前Chunk 通知给用户
                        yield AssistantResponseChunk(
                            type="tool_call", content=tool_info
                        )

            # 首先将完整的回复信息记录到 messages中
            assistant_msg_record = {
                "role": "assistant",
                "content": answer_content,
            }

            # 将所有工具调用信息也记录到 messages中
            if tool_call_info:
                assistant_msg_record["tool_calls"] = [
                    param.to_dict() for param in tool_call_message_params.values()
                ]
            messages.append(assistant_msg_record)

            async for task in asyncio.as_completed(tool_call_tasks):
                result: ToolCallInfo = await task
                messages.append(self.get_tool_result_message(result.result, result.id))
                yield AssistantResponseChunk(type="tool_call_result", content=result)

            if not tool_call_info:
                break


