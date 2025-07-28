import asyncio
from rich import print as rprint
from client.LLMClient import LLMClient


class ChatApp:

    async def chat_loop(self):
        """Run an interactive chat loop"""
        """Process a query using Claude and available tools"""
        messages = [
            {
                "role": "system",
                "content": load_system_prompt(),
            },
        ]

        async with LLMClient() as llmClient:
            print("\nMCP Client Started!")
            print("Type your queries or 'quit' to exit.")

            round = 1
            while True:
                try:
                    print(f"\n\n{'*' * 20} Chat round {round} {'*' * 20}")
                    round += 1

                    query = input("\nQuery: ").strip()

                    if query.lower() == "quit":
                        break

                    if not query:
                        continue

                    messages.append({"role": "user", "content": query})

                    current_type = None
                    async for chunk in llmClient.get_assistant_response(messages):
                        if chunk.type == "answer":
                            if current_type != "answer":
                                current_type = "answer"
                                rprint( "[bold yellow]" + "\n" + "=" * 20 + "完整回复" + "=" * 20 + "[/bold yellow]\n")
                            rprint(chunk.content, end="", flush=True)
                        elif chunk.type == "thinking":
                            if current_type != "thinking":
                                current_type = "thinking"
                                rprint( "[bold cyan]" + "\n" + "=" * 20 + "思考过程" + "=" * 20 + "[/bold cyan]\n")
                            rprint(chunk.content, end="", flush=True)     
                        elif chunk.type == "tool_call":
                            if current_type != "tool_call":
                                current_type = "tool_call"
                                rprint( "[bold green]" + "\n" + "=" * 20 + "工具调用" + "=" * 20 + "[/bold green]\n")
                            rprint(chunk.content, end="", flush=True)        
                except KeyboardInterrupt:
                    break

def load_system_prompt():
    with open("system_prompt.txt", "r") as f:
        return f.read()

if __name__ == "__main__":
    asyncio.run(ChatApp().chat_loop())