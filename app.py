import asyncio
import json
import os
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.callbacks import StdOutCallbackHandler
from langchain_core.messages import (
    SystemMessage,
    ToolMessage,
    HumanMessage,
    AIMessage,
    messages_to_dict,
    messages_from_dict,
)
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp.client.streamable_http import streamable_http_client
from rich import print

from modules import (
    create_llm,
    LOCAL_MCP_SQLITE3_PROMPT,
    get_logger,
    GENERAL_PROMPT,
)
from mcps import MCP_TOOLS

logger = get_logger(name="APP", show_pid=False, show_time=True)
load_dotenv()

CHAT_HISTORY_FILE = Path(__file__).parent / "chat_history.json"
MAX_HISTORY = 30


def _create_message(role: str, content: str):
    if role == "user":
        return HumanMessage(content=content)
    elif role == "assistant":
        return AIMessage(content=content)
    return HumanMessage(content=content)


class MCPAgentModule:
    def __init__(self):
        self.tools = None
        self.llm = None
        self.agent = None
        self.mcp_client = None
        self.system_msg = None
        self.chat_history = []

    async def init(
        self,
        model_provider: Literal["openai", "google", "openrouter", "groq"] = os.getenv("MODEL_PROVIDER"),
        model_name: str = os.getenv("MODEL"),
        model_temperature: Optional[float] = 0.5,
        max_tokens: Optional[int] = 1500,
        system_message: str = LOCAL_MCP_SQLITE3_PROMPT,
    ) -> None:
        logger.info("Initializing MCPAgentModule")
        self.system_msg = SystemMessage(content=system_message)
        self.mcp_client = MultiServerMCPClient(MCP_TOOLS)
        self.tools = await self.mcp_client.get_tools()
        logger.info(f"Loaded {len(self.tools)} tools")

        self.llm = create_llm(
            model_provider=model_provider,
            model_name=model_name,
            model_temperature=model_temperature,
            max_tokens=max_tokens,
        )

        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            # system_prompt=system_message
        )
        self._load_history()

    # --- History Management ---

    def _load_history(self) -> None:
        if CHAT_HISTORY_FILE.exists():
            try:
                data = CHAT_HISTORY_FILE.read_text()
                if data.strip():
                    history_data = json.loads(data)
                    self.chat_history = []
                    for item in history_data:
                        role = item.get("type", "human")
                        content = item.get("data", {}).get("content", "")
                        self.chat_history.append(_create_message(role, content))
                    logger.info(f"Loaded {len(self.chat_history)} messages from history")
            except Exception as e:
                logger.warning(f"Could not load chat history: {e}")
                self.chat_history = []

    def _save_history(self) -> None:
        try:
            history_list = []
            for msg in self.chat_history[-MAX_HISTORY:]:
                role = "human" if isinstance(msg, HumanMessage) else "ai"
                history_list.append({"type": role, "data": {"content": msg.content}})
            import json

            CHAT_HISTORY_FILE.write_text(json.dumps(history_list, indent=2))
        except Exception as e:
            logger.warning(f"Could not save chat history: {e}")

    def _clear_history(self) -> None:
        self.chat_history = []
        if CHAT_HISTORY_FILE.exists():
            CHAT_HISTORY_FILE.unlink()
        logger.info("Chat history cleared")

    # ---  Agent Invocation ---

    async def invoke_agent(self, question: str):
        """
        Prints the response from the agent.
        Args:
            question:

        Returns:

        """
        if self.agent is None:
            logger.info("Initializing agent...")
            await self.init()
            self._load_history()

        human_msg = HumanMessage(content=question)

        messages = [self.system_msg] + self.chat_history + [human_msg]

        inputs = {"messages": messages}

        try:
            agent_response = await self.agent.ainvoke(inputs)
            answer = agent_response["messages"][-1]
            self.chat_history.append(human_msg)
            if isinstance(answer, AIMessage):
                self.chat_history.append(answer)
            else:
                self.chat_history.append(
                    AIMessage(content=answer.content if hasattr(answer, "content") else str(answer))
                )
            if len(self.chat_history) > MAX_HISTORY:
                self.chat_history = self.chat_history[-MAX_HISTORY:]
            self._save_history()

            return answer

        except Exception as e:
            logger.error(f"❌ Agent error: {e}")
            return {"Server Error": {"message": "Failed to invoke agent"}}

    async def agent_stream(self, question: str):
        """Stream agent response with 3 phases: thinking, live stream, full output."""
        if self.agent is None:
            await self.init()
            self._load_history()

        human_msg = HumanMessage(content=question)
        messages = [self.system_msg] + self.chat_history + [human_msg]

        inputs = {"messages": messages}

        tool_responses = []
        reasoning_accumulated = ""
        full_response = ""

        async for token, metadata in self.agent.astream(
            inputs,
            stream_mode="messages",
        ):
            for content in token.content_blocks:
                if isinstance(token, ToolMessage):
                    tool_responses.append(token.content)
                    continue

                if content["type"] == "tool_call_chunk":
                    pass

                if content["type"] == "reasoning":
                    reasoning_text = content["reasoning"]
                    reasoning_accumulated += reasoning_text

                if content["type"] == "text":
                    response_text = content["text"]
                    full_response += response_text

        marker = "Returning structured response:"
        if marker in full_response:
            full_response = full_response.split(marker, 1)[-1].strip()
            if "answer=" in full_response:
                import re

                match = re.search(r'answer="(.*?)"\s+sources=', full_response, re.DOTALL)
                if match:
                    full_response = match.group(1).strip()

        answer_msg = HumanMessage(content=full_response.strip())
        self.chat_history.append(human_msg)
        self.chat_history.append(answer_msg)
        if len(self.chat_history) > MAX_HISTORY:
            self.chat_history = self.chat_history[-MAX_HISTORY:]
        self._save_history()

        print(
            {
                "type": "done",
                "answer": full_response.strip(),
                "full_reasoning": reasoning_accumulated,
                "tool_responses": tool_responses,
            }
        )


async def main():
    agent = MCPAgentModule()
    await agent.init(model_provider="openai", system_message=GENERAL_PROMPT)

    try:
        while True:
            inp = input("\nEnter Your Query: ").strip()
            if not inp:
                continue
            if inp in ["q", "quit", "exit"]:
                logger.info("Exiting...")
                break
            try:
                response = await agent.invoke_agent(question=inp)
                response.pretty_print()
            except Exception as e:
                logger.error(e)
    finally:
        agent._clear_history()


if __name__ == "__main__":
    asyncio.run(main())
