"""
LangChain Agent with Tools using Claude

This example demonstrates how to create an agent that can use tools
(like web search) to answer questions. Claude's tool use capabilities
are well-supported in LangChain.

Prerequisites:
    pip install langchain langchain-anthropic duckduckgo-search
    export ANTHROPIC_API_KEY="your_api_key_here"

Usage:
    python examples/agent_with_tools.py
"""

import os
from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.tools import DuckDuckGoSearchRun


def create_search_agent(
    model_name: str = "claude-3-5-sonnet-20240620",
    temperature: float = 0,
    verbose: bool = True,
) -> AgentExecutor:
    """
    Create an agent with web search capabilities.

    Args:
        model_name: The Claude model to use
        temperature: Controls randomness (0 for more deterministic)
        verbose: Whether to print agent's reasoning steps

    Returns:
        An AgentExecutor that can search the web to answer questions
    """
    # Initialize the Claude model
    llm = ChatAnthropic(model_name=model_name, temperature=temperature)

    # Set up tools
    search_tool = DuckDuckGoSearchRun()
    tools = [search_tool]

    # Create a prompt with a system message and placeholders for agent workflow
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant. Use the tools provided to answer questions. "
                   "Always cite your sources when using search results."),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    # Create the agent using the tool calling agent (recommended for Claude)
    agent = create_tool_calling_agent(llm, tools, prompt)

    # Create the agent executor (the runtime for the agent)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=verbose,
        handle_parsing_errors=True,
    )

    return agent_executor


def main():
    """Run the search agent example."""
    # Ensure API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    # Create the agent
    agent_executor = create_search_agent()

    # Example queries
    queries = [
        "What is the capital of France and what is the current weather there?",
        "Who won the most recent Nobel Prize in Physics?",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"Question: {query}")
        print('='*60)

        result = agent_executor.invoke({"input": query})
        print(f"\nAgent Final Answer: {result['output']}")


if __name__ == "__main__":
    main()
