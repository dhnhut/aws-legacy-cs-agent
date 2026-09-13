"""
Customer Support AI Agent — Starter Code
==========================================
Your task is to complete this file by implementing all sections marked
with # TODO comments.

Reference the step-by-step solution files and INSTRUCTIONS.md for guidance.
Do NOT copy the solution directly — work through each section yourself.

Run locally (after filling in config values):
  uv run main.py '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'

Deploy to AgentCore:
  agentcore deploy

Invoke deployed agent:
  agentcore invoke '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'
"""

# ── Imports ───────────────────────────────────────────────────────────────────
# These imports are provided. Do not remove them.
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
import argparse
import json
import os
import asyncio
import sys
import boto3
from strands.hooks import (
    HookProvider, AfterInvocationEvent, HookRegistry, MessageAddedEvent,
)
import logging
import uuid
from typing import Dict
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands_tools.browser import AgentCoreBrowser


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("CSAI_Agent")

# ── TODO 1 — App Initialisation ───────────────────────────────────────────────
# Create a BedrockAgentCoreApp instance.
# This registers the ASGI server for AgentCore deployment.
# There must be exactly one instance per deployment.
#
# Hint: app = BedrockAgentCoreApp()

# TODO: Create the BedrockAgentCoreApp instance
# app = None  # Replace this line
app = BedrockAgentCoreApp()

# Suppress interactive tool-consent prompts (required in headless deployments).
os.environ["BYPASS_TOOL_CONSENT"] = "true"


# ── TODO 2 — Configuration ────────────────────────────────────────────────────
# Replace the placeholder strings with your actual AWS resource values.
# You collected these in Part 1 of the INSTRUCTIONS.
#
# GATEWAY_URL format: https://<alias>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
# KB_ID       format: 10-character alphanumeric string from the KB console
# REGION:     your AWS region, e.g. "us-east-1"
# MEMORY_ID   format: shown in the AgentCore Memory console

# GATEWAY_URL = "<gateway_url>"   # TODO: Replace with your Gateway URL
# KB_ID = "<kbid>"          # TODO: Replace with your Knowledge Base ID
# REGION = "<region>"        # TODO: Replace with your AWS region
# MEMORY_ID = "<mem_id>"        # TODO: Replace with your Memory ID

GATEWAY_URL = "https://ecom-customersupportgateway-iukqfukqpg.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
KB_ID = "6WYIMJJSR2"
REGION = "us-east-1"
MEMORY_ID = "legacy_cs_mem-O3dMxmDW5L"


# ── TODO 3 — Model and Clients ────────────────────────────────────────────────
# Create:
#   1. A BedrockModel using model_id "global.amazon.nova-2-lite-v1:0"
#   2. A MemoryClient with region_name=REGION
#   3. A boto3 client for the "bedrock-agent-runtime" service in REGION
#
# Hint: model = BedrockModel(model_id=model_id)

model_id = "global.amazon.nova-2-lite-v1:0"

# TODO: Create the BedrockModel instance
# model = None  # Replace this line
model = BedrockModel(model_id=model_id, region_name=REGION)

# TODO: Create the MemoryClient instance
# memory_client = None  # Replace this line
memory_client = MemoryClient(region_name=REGION)

# TODO: Create the boto3 bedrock-agent-runtime client
# _bedrock_runtime = None  # Replace this line
_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


# ── TODO 4 — Namespace Helper ─────────────────────────────────────────────────
# Implement get_namespaces() to return a dict mapping strategy type to
# namespace template string.
def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Return a dict mapping strategy type → namespace template string."""
    # TODO: Implement this function
    # Steps:
    #   1. Call mem_client.get_memory_strategies(memory_id) to get strategy list
    strategies = mem_client.get_memory_strategies(memory_id)

    #   2. Return a dict: { strategy["type"]: strategy["namespaces"][0] for each strategy }
    #
    # Example output:
    #   { "SEMANTIC": "cs_agent/{actorId}/facts",
    #     "USER_PREFERENCE": "cs_agent/{actorId}/preferences" }
    return {
        strategy["type"]: (strategy.get("namespaceTemplates")
                           or strategy["namespaces"])[0]
        for strategy in strategies
    }


# ── TODO 5 — Memory Hook ──────────────────────────────────────────────────────
# Implement MemoryHook, a HookProvider subclass that adds long-term memory.
#
# The class needs:
#   __init__(self, actor_id, session_id, memory_client, memory_id)
#     — store all four as instance attributes
#     — call get_namespaces() and store the result as self.namespaces
#
#   retrieve_customer_context(self, event: MessageAddedEvent)
#     — only runs for plain-text user messages (not tool results)
#     — for each strategy namespace, call memory_client.retrieve_memories(
#          memory_id, namespace (formatted with actorId), query, top_k=5)
#     — collect non-empty memory texts tagged with their strategy type
#     — if any memories found, prepend them to the user message as:
#          "Customer Context:\n<memories>\n\n<original_message>"
#
#   save_support_interaction(self, event: AfterInvocationEvent)
#     — walk the message list backwards to find the last plain-text user
#       query and the last assistant response
#     — call memory_client.create_event(memory_id, actor_id, session_id,
#          messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")])
#
#   register_hooks(self, registry: HookRegistry)
#     — register retrieve_customer_context on MessageAddedEvent
#     — register save_support_interaction on AfterInvocationEvent
class MemoryHook(HookProvider):
    """Long-term memory hook for the customer support agent."""

    def __init__(
        self,
        actor_id: str,
        session_id: str,
        memory_client: MemoryClient,
        memory_id: str,
    ):
        # TODO: Store actor_id, session_id, memory_id, memory_client as attributes
        self.actor_id = actor_id
        self.session_id = session_id
        self.memory_client = memory_client
        self.memory_id = memory_id

        # TODO: Call get_namespaces() and store the result as self.namespaces
        self.namespaces = get_namespaces(memory_client, memory_id)

    def retrieve_customer_context(self, event: MessageAddedEvent):
        """Retrieve relevant memories and prepend them to the user message."""
        # TODO: Implement memory retrieval
        # Steps:
        #   1. Get the last message from event.agent.messages
        message = event.message
        #   2. Check it is a user message and not a tool result
        if message["role"] != "user":
            return
        #   3. Extract the user query text
        content = message.get("content", [])
        if any("toolResult" in block for block in content):
            return
        query = "\n".join(block["text"]
                          for block in content if "text" in block)
        if not query:
            return

        context_lines = []
        #   4. For each namespace in self.namespaces, call retrieve_memories()
        for strategy_type, namespace_template in self.namespaces.items():
            namespace = namespace_template.replace(
                "{actorId}", self.actor_id
            ).replace("{sessionId}", self.session_id)
            records = self.memory_client.retrieve_memories(
                self.memory_id, namespace=namespace, query=query, top_k=5,
            )
        #   5. Collect non-empty memory texts with strategy type tags
            for record in records:
                text = record.get("content", {}).get("text", "")
                if text:
                    context_lines.append(f"[{strategy_type}] {text}")

        if not context_lines:
            return

        #   6. If any found, prepend them to the user message
        memories_block = "\n".join(context_lines)
        for block in content:
            if "text" in block:
                block["text"] = f"Customer Context:\n{memories_block}\n\n{block['text']}"
                break

    def save_support_interaction(self, event: AfterInvocationEvent):
        """Save the completed turn to memory after the agent responds."""
        # TODO: Implement memory saving
        # Steps:
        #   1. Get messages from event.agent.messages
        messages = event.agent.messages

        #   2. Walk backwards to find the last user query (plain text)
        #      and the last assistant response
        user_query = None
        assistant_response = None
        for message in reversed(messages):
            content = message.get("content", [])
            if any("toolResult" in block or "toolUse" in block for block in content):
                continue
            text = "\n".join(block["text"]
                             for block in content if "text" in block)
            if not text:
                continue
            if assistant_response is None and message["role"] == "assistant":
                assistant_response = text
            elif user_query is None and message["role"] == "user":
                user_query = text
            if user_query and assistant_response:
                break

        if not (user_query and assistant_response):
            return
        #   3. Call memory_client.create_event() with both messages
        self.memory_client.create_event(
            self.memory_id,
            self.actor_id,
            self.session_id,
            messages=[(user_query, "USER"), (assistant_response, "ASSISTANT")],
        )

    def register_hooks(self, registry: HookRegistry) -> None:  # type: ignore
        """Register both memory callbacks."""
        # TODO: Register retrieve_customer_context on MessageAddedEvent
        registry.add_callback(
            MessageAddedEvent, self.retrieve_customer_context)

        # TODO: Register save_support_interaction on AfterInvocationEvent
        registry.add_callback(AfterInvocationEvent,
                              self.save_support_interaction)


# ── TODO 6 — Knowledge Base Tool ─────────────────────────────────────────────
# Implement search_knowledge_base(query) using the @tool decorator.
#
# The docstring is the tool description — the model uses it to decide when
# to call this tool, so keep it clear and accurate.
@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Amazon product catalog and support knowledge base.
    Use this for product specifications, return policies, warranty
    information, loyalty program details, and order status definitions.

    Args:
        query: The question or topic to search for

    Returns:
        Relevant information retrieved from the knowledge base
    """

    # TODO: Implement the Knowledge Base search
    #
    # Steps:
    #   1. Guard: if KB_ID is empty return "Knowledge base not configured."
    if not KB_ID:
        return "Knowledge base not configured."

    #   2. Call _bedrock_runtime.retrieve(
    #          knowledgeBaseId=KB_ID,
    #          retrievalQuery={"text": query}
    #      )
    response = _bedrock_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
    )
    #   3. Extract resp["retrievalResults"]; return a message if empty
    results = response.get("retrievalResults", [])
    if not results:
        return "No relevant information found in the knowledge base."

    #   4. Join the text chunks with "\n---\n" and return the result
    chunks = [r["content"]["text"] for r in results]
    return "\n---\n".join(chunks)


# ── TODO 7 — Loyalty Discount Tool (Code Interpreter) ────────────────────────
# Implement calculate_loyalty_discount() using the @tool decorator.
#
# The tool must:
#   1. Build a self-contained Python code string that:
#        • Defines earn_rates: {"standard": 1, "device": 2, "fresh": 5}
#        • Defines tier_rates: {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
#        • Calculates points_redeemed (floor to nearest 500, cap at 50% of order)
#        • Calculates tier_discount (applied to subtotal after points)
#        • Calculates final_total, total_savings, points_earned, remaining_points
#        • Prints a JSON result dict
#   2. Execute the code with code_session(REGION).invoke("executeCode", {...})
#      using language="python" and clearContext=True
#   3. Return the first result event as a JSON string
#   4. Include a fallback that computes only the tier discount if the
#      Code Interpreter is unavailable

@tool
def calculate_loyalty_discount(
    loyalty_points: int,
    tier: str,
    order_total: float,
    product_category: str = "standard",
) -> str:
    """
    Calculate the loyalty discount for a customer order using the
    AgentCore Code Interpreter. Runs exact arithmetic in a secure sandbox.

    Args:
        loyalty_points:   Customer's current points balance
        tier:             Customer tier — Silver, Gold, or Platinum
        order_total:      Order total in USD
        product_category: standard, device, or fresh

    Returns:
        Full discount breakdown and final price
    """
    # TODO: Build the code string (use an f-string to inject the arguments)
    code = ""  # Replace with your code string
    code = f"""
import json

earn_rates = {{"standard": 1, "device": 2, "fresh": 5}}
tier_rates = {{"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}}

loyalty_points = {loyalty_points}
tier = "{tier}"
order_total = {order_total}
product_category = "{product_category}"

tier_discount_pct = tier_rates.get(tier, 0.0)

# 100 points = $1; cap redemption at 50% of the order, floor to nearest 500 points
max_redeemable_points = int(order_total * 0.5 * 100)
points_redeemed = max(0, min(loyalty_points, max_redeemable_points) // 500 * 500)
redeemed_value = points_redeemed / 100

subtotal = order_total - redeemed_value
tier_discount = subtotal * tier_discount_pct
final_total = subtotal - tier_discount
total_savings = order_total - final_total

points_earned = int(final_total * earn_rates.get(product_category, 1))
remaining_points = loyalty_points - points_redeemed + points_earned

result = {{
    "points_redeemed": points_redeemed,
    "tier_discount_pct": tier_discount_pct,
    "final_total": round(final_total, 2),
    "remaining_points": remaining_points,
    "total_savings": round(total_savings, 2),
    "points_earned": points_earned,
}}

print(json.dumps(result))
"""

    try:
        # TODO: Execute the code using code_session and return the result
        with code_session(REGION) as code_client:
            response = code_client.invoke("executeCode", {
                "code": code,
                "language": "python",
                "clearContext": True,
            })
            for event in response["stream"]:
                if "result" in event:
                    return event["result"]["content"][0]["text"]
            return json.dumps({"error": "No result returned from code interpreter"})

    except Exception as e:
        # TODO: Implement fallback calculation using tier discount only
        tier_rates = {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
        tier_discount_pct = tier_rates.get(tier, 0.0)
        tier_discount = order_total * tier_discount_pct
        final_total = order_total - tier_discount
        return json.dumps({
            "points_redeemed": 0,
            "tier_discount_pct": tier_discount_pct,
            "final_total": round(final_total, 2),
            "remaining_points": loyalty_points,
            "note": f"Code interpreter unavailable ({e}); tier-only discount applied.",
        })


# ── TODO 8 — Agent Entrypoint ─────────────────────────────────────────────────
# Implement the invoke() function decorated with @app.entrypoint.
#
# Steps:
#   1. Extract user_input, actor_id, and session_id from the payload
#      (generate a UUID if session_id is missing)
#   2. Instantiate MemoryHook for this actor/session
#   3. Instantiate AgentCoreBrowser(region=REGION)
#   4. Build the tools list: [search_knowledge_base, calculate_loyalty_discount,
#                              agent_core_browser.browser]
#   5. Connect to the Gateway via MCPClient, load gateway_tools, extend tools list
#   6. Create and invoke the Agent with all tools, hooks, and system_prompt
#   7. Return the text from the first content block of the response
#   8. Handle exceptions gracefully

SYSTEM_PROMPT = """
# You are an intelligent customer support assistant for an e-commerce platform name Ecom.

## Use tools when appropriate.

### Knowledge Base
Product, policy, loyalty member, and troubleshooting questions are answered from the
CustomerSupportKB knowledge base, reachable as the `customer-support-kb___Retrieve`
and `customer-support-kb___AgenticRetrieveStream` tools on the support gateway.
Retrieve before you answer any question about product specs, pricing, warranty
terms, the return or refund policy, shipping, or how to fix a device — never
answer those from your own knowledge. Prefer `Retrieve` for a single lookup and
`AgenticRetrieveStream` for questions that span several documents.

Ground your answer in the retrieved passages and cite the product or policy name
you drew it from. If retrieval comes back with nothing relevant, say the
knowledge base does not cover it rather than guessing.

### Loyalty Discounts: always compute with the tool
Use the `calculate_loyalty_discount` tool whenever a customer asks what a discount,
redemption, or final price actually works out to — never do the arithmetic yourself.
The knowledge base is for describing the program (tier thresholds, benefits, earn and
redemption rules); the tool is for any concrete number. Report its figures as returned.

### Order Lookups, Refunds and Return Labels: go to their own tools
Order status, order history, and customer profile lookups are handled by the
`order-tracker___*` tools on the support gateway. Refund initiation, refund
status checks, and return label generation are handled by the
`refund-processor___*` tools (`initiate_refund`, `check_refund_status`,
`get_return_label`). Always use these tools for concrete order/refund data —
never guess an order status or make up a refund confirmation.

## You have PERSISTENT MEMORY: you remember each customer's preferences, past product, orders,
and interests across multiple conversations.

MEMORY-AWARE BEHAVIOUR
- When a <user_context> block appears at the start of the user's message, it contains facts and preferences retrieved from past conversations.
- Use this context to personalise your recommendations naturally.
- Reference past context: "Based on your interest in Speakers..."
- Never ask the Customer to repeat information they've already shared.

Be warm, attentive, and genuinely helpful — like a trusted assistant who has known the customer for years.
"""

tools = [search_knowledge_base, calculate_loyalty_discount]


@app.entrypoint
async def invoke(payload, context=None):
    """
    Main handler called by AgentCore for every incoming request.

    Expected payload keys:
      prompt      (str, required) — the customer's message
      customer_id (str, optional) — unique customer identifier
      session_id  (str, optional) — session identifier; generated if absent
    """
    # TODO: Implement the agent invocation

    prompt = payload.get("prompt", "")
    if not prompt:
        raise ValueError("Error: 'prompt' is required in the payload.")
    actor_id = payload.get("customer_id") or payload.get(
        "actor_id") or str(uuid.uuid4())
    session_id = payload.get("session_id", str(uuid.uuid4()))

    memory_hook = MemoryHook(
        actor_id=actor_id,
        session_id=session_id,
        memory_client=memory_client,
        memory_id=MEMORY_ID,
    )

    agent_core_browser = AgentCoreBrowser(region=REGION)
    tools.append(agent_core_browser.browser)

    # - Code uses `app.run()` as the main entry point.
    # - Submitted test output shows the agent responding to an `agentcore invoke` command without errors.
    mcp_client = MCPClient(lambda: streamable_http_client(GATEWAY_URL))

    with mcp_client:
        gateway_tools = mcp_client.list_tools_sync()
        tools.extend(gateway_tools)

        agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
            hooks=[memory_hook],
            state={"session_id": session_id, "actor_id": actor_id},
        )

        response = agent(prompt)

    return response


# ── CLI entry point (do not modify) ──────────────────────────────────────────
def main():
    """Run one invocation from the command line for local testing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=str)
    args = parser.parse_args()
    response = asyncio.run(invoke(json.loads(args.payload)))
    print(response)


if __name__ == "__main__":
    # run from the repo root, where `uv` is installed in the virtual environment.
    # `agentcore deploy` / the AgentCore runtime invoke this file with no extra
    # CLI args, so app.run() (the HTTP server) starts.
    # passes a JSON payload arg, so main() (one-shot CLI invocation) runs instead.
    if len(sys.argv) > 1:
        # `uv run src/customer_support_agent/main.py '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'`
        main()
    else:
        # `uv run agentcore invoke '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'`
        app.run()
