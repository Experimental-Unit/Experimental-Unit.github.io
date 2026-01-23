# LangChain + Claude Examples

Standalone examples demonstrating how to use Claude with LangChain for various use cases.

## Prerequisites

1. Install dependencies:
   ```bash
   pip install langchain langchain-anthropic duckduckgo-search
   ```

2. Set your Anthropic API key:
   ```bash
   export ANTHROPIC_API_KEY="your_api_key_here"
   ```

## Examples

### Basic LCEL Chain (`basic_chain.py`)

A simple chain that connects a prompt template and Claude for English-to-French translation.

**Key concepts:**
- `ChatAnthropic` - Initialize Claude model
- `ChatPromptTemplate` - Define structured prompts
- `StrOutputParser` - Parse string responses
- LCEL pipe syntax: `prompt | llm | output_parser`

```bash
python examples/basic_chain.py
```

### Agent with Tools (`agent_with_tools.py`)

An agent that uses web search to answer questions with real-time information.

**Key concepts:**
- `create_tool_calling_agent` - Create tool-enabled agents
- `AgentExecutor` - Runtime for executing agents
- `DuckDuckGoSearchRun` - Web search tool

```bash
python examples/agent_with_tools.py
```

## Model Selection

These examples use `claude-3-5-sonnet-20240620` by default. You can change the model:

```python
llm = ChatAnthropic(model_name="claude-sonnet-4-20250514", temperature=0.7)
```

Available Claude models:
- `claude-sonnet-4-20250514` - Balanced performance
- `claude-3-5-sonnet-20240620` - Fast, capable
- `claude-3-opus-20240229` - Most capable

## Related Resources

- [LangChain Anthropic Docs](https://python.langchain.com/docs/integrations/chat/anthropic/)
- [Anthropic API Docs](https://docs.anthropic.com/)
- See the main `pipeline/` directory for a production example
