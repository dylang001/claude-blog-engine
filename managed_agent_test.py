import os
from anthropic import Anthropic, AuthenticationError, BadRequestError


api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise RuntimeError(
        "Set ANTHROPIC_API_KEY first. If an old key was pasted anywhere, rotate it "
        "in the Anthropic Console before using this script."
    )

client = Anthropic(api_key=api_key)
model_candidates = [
    os.getenv("ANTHROPIC_AGENT_MODEL"),
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-sonnet-4-5",
]
model_candidates = [model for model in model_candidates if model]

print("ANTHROPIC_API_KEY is set; creating managed agent session...")

agent = None
for model in model_candidates:
    try:
        print(f"Trying model: {model}")
        agent = client.beta.agents.create(
            name="Blog Engine Agent",
            model={"id": model},
            system="You are an autonomous coding agent helping run and maintain a blog engine.",
            tools=[{"type": "agent_toolset_20260401"}],
        )
        print(f"Created agent {agent.id} with {model}")
        break
    except AuthenticationError:
        raise
    except BadRequestError as exc:
        message = str(exc)
        if "model is not supported" not in message and "`model.id`" not in message:
            raise
        print(f"Model rejected by Managed Agents beta: {model}")

if agent is None:
    raise RuntimeError(
        "No candidate model was accepted. Try setting ANTHROPIC_AGENT_MODEL to a "
        "Managed Agents-supported model from your Anthropic Console/workspace."
    )

environment = client.beta.environments.create(
    name="blog-engine-env",
    config={"type": "cloud", "networking": {"type": "unrestricted"}},
)

session = client.beta.sessions.create(
    agent=agent.id,
    environment_id=environment.id,
    title="Blog engine setup session",
)

with client.beta.sessions.events.stream(session.id) as stream:
    client.beta.sessions.events.send(
        session.id,
        events=[{
            "type": "user.message",
            "content": [{"type": "text", "text": "Inspect this repo and run setup; then summarize steps taken."}],
        }],
    )

    for event in stream:
        if event.type == "agent.message":
            for block in getattr(event, "content", []):
                text = getattr(block, "text", None)
                if text:
                    print(text, end="")
        elif event.type == "agent.tool_use":
            print(f"\n[tool] {getattr(event, 'name', 'unknown')}")
        elif event.type == "session.status_idle":
            print("\nDone.")
            break

print("\nSession complete.")
