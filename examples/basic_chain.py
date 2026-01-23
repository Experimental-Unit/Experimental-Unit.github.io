"""
Basic LangChain Chain with Claude

This example demonstrates a simple LCEL (LangChain Expression Language) chain
that connects a prompt template and the Claude model to generate a response.

Prerequisites:
    pip install langchain langchain-anthropic
    export ANTHROPIC_API_KEY="your_api_key_here"

Usage:
    python examples/basic_chain.py
"""

import os
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


def create_translation_chain(
    model_name: str = "claude-3-5-sonnet-20240620",
    temperature: float = 0.7,
) -> object:
    """
    Create a translation chain using Claude.

    Args:
        model_name: The Claude model to use
        temperature: Controls randomness in responses (0.0-1.0)

    Returns:
        An LCEL chain for English to French translation
    """
    # Initialize the Claude model
    llm = ChatAnthropic(model_name=model_name, temperature=temperature)

    # Define a prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant that translates English to French."),
        ("human", "{user_input}")
    ])

    # Define an output parser to get a simple string response
    output_parser = StrOutputParser()

    # Create the chain using LangChain Expression Language (LCEL)
    chain = prompt | llm | output_parser

    return chain


def main():
    """Run the translation chain example."""
    # Ensure your ANTHROPIC_API_KEY environment variable is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    # Create the chain
    chain = create_translation_chain()

    # Invoke the chain with input
    user_input = "I love programming."
    response = chain.invoke({"user_input": user_input})

    print(f"User Input: {user_input}")
    print(f"Claude Response: {response}")

    # Additional examples
    examples = [
        "Hello, how are you?",
        "The weather is beautiful today.",
        "Machine learning is fascinating.",
    ]

    print("\n--- Additional Examples ---")
    for text in examples:
        result = chain.invoke({"user_input": text})
        print(f"\nEnglish: {text}")
        print(f"French: {result}")


if __name__ == "__main__":
    main()
