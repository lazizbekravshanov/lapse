"""The agent door of the hub: a model may ask questions, but only through the hub's
read-only tools, and no number reaches the reader unless a tool produced it.

    tools.py        what the agent can do (and nothing else)
    guard.py        the number check on every answer
    harness.py      the model/tool loop, with a fallback that needs no model
    planner.py      the rule-based stand-in used when there is no model
    models.py       adapters: Claude, any OpenAI-compatible server, a scripted model for tests
    mcp_server.py   the same tools for any MCP client
"""
