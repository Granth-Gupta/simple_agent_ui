import asyncio
import os
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.1)

server_params = StdioServerParameters(
    command="npx",
    env={
        "FIRECRAWL_API_KEY": os.getenv("FIRECRAWL_API_KEY"),
    },
    args=["firecrawl-mcp"],
)


async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            agent = create_react_agent(model, tools)

            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that can scrape websites, crawl pages, and extract data using Firecrawl tools. Think step by step and use the appropriate tools to help the user.",
                }
            ]

            print("Available Tools -", *[tool.name for tool in tools])
            print("-" * 60)

            while True:
                try:
                    user_input = input("\nYou: ")
                    if user_input.lower() == "quit":
                        print("Goodbye!")
                        break
                except EOFError:
                    print("\nEOF encountered, exiting.")
                    break
                except Exception as e:
                    print(f"An error occurred during input: {e}")
                    break

                messages.append({"role": "user", "content": user_input[:175000]})

                try:
                    agent_response = await agent.ainvoke({"messages": messages})

                    ai_message_content = ""
                    for msg in agent_response["messages"]:
                        if isinstance(msg, AIMessage) and msg.tool_calls:
                            print("\n--- LLM USED A TOOL! ---")
                            for tool_call in msg.tool_calls:
                                print(f"  Tool Name: {tool_call}")
                            print("------------------------")
                        elif isinstance(msg, ToolMessage):
                            print(f"\n--- TOOL OUTPUT ({msg.name}): ---")
                            print(msg.content[:100])
                            print("---------------------------")
                        elif isinstance(msg, AIMessage) and msg.content:
                            ai_message_content = msg.content

                    if ai_message_content:
                        print("\nAgent:", ai_message_content)
                    else:
                        print(
                            "\nAgent: (No direct textual response, perhaps only tool calls were made or an error occurred in generation.)"
                        )

                except Exception as e:
                    print(f"Error during agent invocation: {e}")


if __name__ == "__main__":
    asyncio.run(main())