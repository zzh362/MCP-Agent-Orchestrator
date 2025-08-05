import asyncio
import json
import os
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat.chat_completion_chunk import ChoiceDelta, ChoiceDeltaToolCall
from rich import print as rprint

from client.LLMClient import LLMClient
from util.data import ToolCallInfo
from util.constants import SERVER_CONFIG_FILE

load_dotenv()  # load environment variables from .env


def load_system_prompt():
    with open("system_prompt.txt", "r") as f:
        return f.read()


def updateSystemPrompt(system_prompt, history):
    """
    更新对话历史中的系统提示词
    
    该函数负责维护对话历史中系统提示词的正确位置和内容。
    如果历史记录为空，则添加系统提示词；如果第一条不是系统提示词，
    则在开头插入；否则更新现有的系统提示词内容。
    
    参数:
        system_prompt (str): 新的系统提示词内容
        history (list): 对话历史记录列表，每个元素为包含'role'和'content'键的字典
    
    返回值:
        无返回值，直接修改传入的history列表
    """
    # 检查历史记录是否为空
    if len(history) == 0:
        history.append({"role": "system", "content": system_prompt})
    # 如果第一条记录不是系统角色，则在开头插入系统提示词
    elif history[0]["role"] != "system":
        history.insert(0, {"role": "system", "content": system_prompt})
    # 如果第一条记录已经是系统角色，则更新其内容
    else:
        history[0]["content"] = system_prompt


exit_stack = AsyncExitStack()
init_event = asyncio.Event()
llm_client: Optional[LLMClient] = None


async def initialize_client():
    global llm_client
    llm_client = await exit_stack.enter_async_context(
        LLMClient(mcp_config_file=SERVER_CONFIG_FILE)
    )
    init_event.set()


async def cleanup_client():
    await exit_stack.aclose()


# System message for the chat
system_message = load_system_prompt()

"""
构建MCP聊天助手的Gradio界面

该代码块使用Gradio库创建一个聊天助手的Web界面，包含聊天区域、输入框、
系统消息显示和内部历史记录查看等功能组件。
"""

with gr.Blocks(title="MCP Chat Assistant") as demo:
    # 显示应用标题
    gr.Markdown("# MCP Chat Assistant")

    # 注册应用加载和卸载时的回调函数
    demo.load(initialize_client)
    demo.unload(cleanup_client)

    # 显示聊天区域标题
    gr.Markdown("# Chat with an AI assistant")
    
    # 创建聊天机器人组件，用于显示对话历史
    chatbot = gr.Chatbot(height=700, type="messages")

    # 创建消息输入框，用户在此输入问题或指令
    msg = gr.Textbox(
        placeholder="Ask a question or request an action...",
        show_label=False,
        container=False,
    )

    # 创建操作按钮行
    with gr.Row():
        clear = gr.Button("Clear Chat")
        reset_system = gr.Button("Reset System Message")

    # 创建侧边栏信息显示区域
    with gr.Row():
        with gr.Column(scale=1):
            # 显示内部历史记录标题和内容框
            gr.Markdown("## Internal History")
            internal_history = gr.Textbox(
                value="[]", lines=30, show_label=False, container=False
            )
        with gr.Column(scale=1):
            # 显示系统消息标题和内容框
            gr.Markdown("## System Message")
            system_prompt = gr.Textbox(
                value=system_message, show_label=False, container=False, lines=30
            )

    def onUserSubmit(user_input, history):
        # Add user message to history
        return "", history + [{"role": "user", "content": user_input}]

    def tryCompleteThinkingMessage(history):
        try:
            if (
                len(history) > 0
                and history[-1].metadata.get("title") == "thinking"
                and history[-1].metadata.get("status") == "pending"
            ):
                history[-1].metadata["status"] = "done"
        except Exception as e:
            pass

    async def getCompletion(
        history: list[gr.ChatMessage], system_prompt, internal_history
    ):
        """
        异步函数，用于获取聊天完成结果。该函数处理用户消息、系统提示，并与LLM客户端交互以生成助手响应，
        同时支持工具调用和结果展示。

        参数:
            history (list[gr.ChatMessage]): 当前会话的聊天历史记录，包含用户和助手的消息。
            system_prompt (str): 系统提示信息，用于指导模型行为。
            internal_history (str): 内部历史记录的JSON字符串表示，用于维护内部状态。

        返回:
            tuple[list[gr.ChatMessage], str]: 更新后的聊天历史记录和内部消息的JSON格式字符串。
        """

        # 等待初始化事件完成
        await init_event.wait()

        # 解析内部历史记录并更新系统提示
        internal_messages = json.loads(internal_history)
        updateSystemPrompt(system_prompt, internal_messages)

        # 将最新的用户消息添加到内部消息列表中
        internal_messages.append(history[-1])
        rprint(internal_messages)

        # 处理模型响应并根据响应类型更新聊天历史
        # LLMClient 会自动将助手和工具消息添加到 internal_messages 中，因此此处无需手动更新
        current_type = None
        tool_call_info = {}
        async for response in llm_client.get_assistant_response(internal_messages):
            if response.type == "thinking":
                # 处理模型思考过程中的中间输出
                if current_type != "thinking":
                    current_type = "thinking"
                    new_message = gr.ChatMessage(
                        role="assistant",
                        content=response.content,
                        metadata={"title": "thinking", "status": "pending"},
                    )
                    history.append(new_message)
                else:
                    thinking_message = history[-1]
                    thinking_message.content += response.content

            if response.type == "answer":
                # 处理最终回答内容
                if current_type != "answer":
                    tryCompleteThinkingMessage(history)

                    current_type = "answer"
                    new_message = gr.ChatMessage(
                        role="assistant",
                        content=response.content,
                    )
                    history.append(new_message)
                else:
                    answer_message = history[-1]
                    answer_message.content += response.content

            if response.type == "tool_call":
                # 处理工具调用请求
                print(f"tool_call_info from app: {response}")
                if current_type != "tool_call":
                    current_type = "tool_call"
                    tryCompleteThinkingMessage(history)

                tool_info: ToolCallInfo = response.content
                new_message = gr.ChatMessage(
                    role="assistant",
                    content=f"calling, args: {str(tool_info.args)}",
                    metadata={
                        "title": f"Calling tool {tool_info.name} ...",
                        "status": "pending",
                    },
                )
                history.append(new_message)
                tool_call_info[tool_info.id] = new_message

            if response.type == "tool_call_result":
                # 处理工具调用结果并更新对应的消息状态
                # print(f"tool_call_result from app: {response.content}")
                tool_call_result: ToolCallInfo = response.content
                tool_call_message = tool_call_info[tool_call_result.id]
                tool_call_message.content = tool_call_result.result.content[0].text
                tool_call_message.metadata["status"] = "done"

            # 每次迭代都返回当前历史记录和内部消息状态
            yield history, json.dumps(internal_messages, indent=4)

        # 最终再返回一次完整的结果
        yield history, json.dumps(internal_messages, indent=4)

    def reset_system_message():
        return system_message["content"]

    def clear_chat():
        return [], "[]"

    msg.submit(onUserSubmit, [msg, chatbot], [msg, chatbot], queue=False).then(
        getCompletion,
        [chatbot, system_prompt, internal_history],
        [chatbot, internal_history],
    )

    clear.click(clear_chat, None, [chatbot, internal_history], queue=False)
    reset_system.click(reset_system_message, None, system_prompt, queue=False)

# Start the Gradio app

if __name__ == "__main__":
    demo.launch()
