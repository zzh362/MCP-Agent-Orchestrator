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
    if len(history) == 0:
        history.append({"role": "system", "content": system_prompt})
    elif history[0]["role"] != "system":
        history.insert(0, {"role": "system", "content": system_prompt})
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

# Create the Gradio interface
with gr.Blocks(title="MCP Chat Assistant") as demo:
    gr.Markdown("# MCP Chat Assistant")

    demo.load(initialize_client)
    demo.unload(cleanup_client)

    gr.Markdown("# Chat with an AI assistant")
    chatbot = gr.Chatbot(height=700, type="messages")

    msg = gr.Textbox(
        placeholder="Ask a question or request an action...",
        show_label=False,
        container=False,
    )

    with gr.Row():
        clear = gr.Button("Clear Chat")
        reset_system = gr.Button("Reset System Message")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Internal History")
            internal_history = gr.Textbox(
                value="[]", lines=30, show_label=False, container=False
            )
        with gr.Column(scale=1):
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
        await init_event.wait()

        internal_messages = json.loads(internal_history)
        updateSystemPrompt(system_prompt, internal_messages)

        # append user message to internal messages
        internal_messages.append(history[-1])
        rprint(internal_messages)

        # Process the message and update history with bot response
        # the LLMClient will add assistant and tool messages to internal_messages, so no need to update here
        current_type = None
        tool_call_info = {}
        async for response in llm_client.get_assistant_response(internal_messages):
            if response.type == "thinking":
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
                # print(f"tool_call_result from app: {response.content}")
                tool_call_result: ToolCallInfo = response.content
                tool_call_message = tool_call_info[tool_call_result.id]
                tool_call_message.content = tool_call_result.result.content[0].text
                tool_call_message.metadata["status"] = "done"

            yield history, json.dumps(internal_messages, indent=4)

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
