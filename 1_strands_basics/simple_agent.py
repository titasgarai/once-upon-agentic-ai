import logging
from strands import Agent

# TODO: Step 1 - Add debug logging to see what your agent is thinking
logging.basicConfig(level=logging.DEBUG)

# TODO: Step 2 - Create the agent with the following system prompt: "You are a game master for a fantasy role-playing game"
agent = Agent(system_prompt="You are a game master for a fantasy role-playing game")

# TODO: Step 3 - Invoke your agent with a basic query such as "Hi, I am an adventurer ready for adventure!"
response = agent("Hi, I am an adventurer ready for adventure!")
print("\n=== Agent Response ===")
print(response)
