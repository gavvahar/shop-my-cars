"""Throwaway spike (Task 2): verify qwen2.5:7b reliably triggers correct
LangChain tool calls via the self-hosted Ollama instance.

Run directly: python Python/scripts/spike_tool_calling.py
"""
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

OLLAMA_BASE_URL = "http://192.168.1.14:11434"
MODEL = "qwen2.5:7b"


@tool
def get_car_price(make: str, model: str) -> str:
    """Look up the price of a car by make and model."""
    return f"The {make} {model} typically costs $22,500."


@tool
def get_weather(city: str) -> str:
    """Look up the current weather for a city."""
    return f"It's sunny and 72F in {city}."


TEST_PROMPTS = [
    "What's the price of a 2016 Toyota Corolla?",
    "How much does a Honda Civic cost?",
    "What's the weather like in Chicago?",
    "Is it raining in Seattle today?",
    "Tell me the price of a Ford F-150 and also the weather in Austin.",
    "Compare the price of a Tesla Model 3 to a Nissan Leaf.",
    "What's your favorite color?",
    "What's 15 times 23?",
]


def main():
    llm = ChatOllama(model=MODEL, base_url=OLLAMA_BASE_URL)
    llm_with_tools = llm.bind_tools([get_car_price, get_weather])

    for i, prompt in enumerate(TEST_PROMPTS, start=1):
        response = llm_with_tools.invoke(prompt)
        print(f"--- Prompt {i}: {prompt}")
        if response.tool_calls:
            for call in response.tool_calls:
                print(f"  called: {call['name']}  args: {call['args']}")
        else:
            print(f"  no tool called — response: {response.content[:200]}")
        print()


if __name__ == "__main__":
    main()
