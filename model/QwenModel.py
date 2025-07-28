from .ModelInterface import ModelInterface

import os
from openai import AsyncOpenAI
from dotenv import load_dotenv


MODEL_NAME = "qwen3-235b-a22b"
load_dotenv()  # load environment variables from .env

class QwenModel(ModelInterface):
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    async def get_chat_completion(self, messages, tools):
        response = await self.client.chat.completions.create(
            model=MODEL_NAME,
            max_tokens=1000,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            extra_body={"enable_thinking": True, "thinking_budget": 500},
            stream=True,
            parallel_tool_calls=True,
        )
        return response