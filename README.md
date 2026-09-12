# Agent Deployment & Tool Integration

This is legacy app, using obsoleted [Bedrock AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)

## Deploy an AI agent to a cloud runtime

### Code includes a `BedrockAgentCoreApp` instance created at module level.

- An async `invoke` function uses the `@app.entrypoint` decorator.
- Code uses `app.run()` as the main entry point.
- Submitted test output shows the agent responding to an `agentcore invoke` command without errors.

### Integrate external tools using the Model Context Protocol

- Code connects to a Gateway endpoint using `MCPClient`.
- Code loads Gateway tools and adds them to the agent's tools list.
- Submitted test conversation log includes successful invocations of at least two distinct Gateway-backed tools (one API-based target, one Lambda-based target).
- Each tool invocation in the test log returns a well-formed response (not an error or empty result).

## Agent Intelligence

### Implement Retrieval Augmented Generation with a knowledge base

- Code includes a `search_knowledge_base` function using the `@tool` decorator.
- The tool function calls the Retrieve API.
- The tool function joins retrieved text chunks and returns them as a single formatted string.
- Code includes a guard clause that returns a descriptive message when `KB_ID` is not configured.
- The `@tool`-decorated function includes a docstring that describes when the agent should call it.

### Implement cross-session agent memory with retrieval and persistence

- Code includes a `get_namespaces` function that fetches strategy types and namespace templates from the memory resource, using `namespaceTemplates` or the legacy `namespaces` field.
- A `MemoryHook` class extends `HookProvider` and registers hooks via a `register_hooks` method.
- Code includes a `retrieve_customer_context` function that queries all strategy namespaces, tags memories by strategy type, and prepends them to the user message.
- Code includes a `save_support_interaction` function that extracts the last user query and assistant response and calls `memory_client.create_event()`.
- Submitted test conversation log demonstrates cross-session recall: two separate sessions using the same customer ID, where the second session retrieves information stored in the first.

### Execute computational tasks via a sandboxed code interpreter

- Code includes a `calculate_loyalty_discount` function using the `@tool` decorator.
- The tool function builds a self-contained Python code string that encodes business rules for points redemption, tier discounts, and earn rates.
- Code executes the code string via `code_session(REGION).invoke("executeCode", ...)` with `clearContext=True`.
- Code includes a fallback path that computes a tier-only discount when the code interpreter is unavailable.
- The tool returns a structured result containing all of the following fields: `points_redeemed`, `tier_discount_pct`, `final_total`, `remaining_points`.

### Enable web browsing capabilities through a browser tool

- Code instantiates `AgentCoreBrowser` with the AWS region.
- Code adds the agentcore browser to the agent's tools list.
- Submitted test output shows the agent retrieving content from a live web page.

## Code Quality & Reflection

### Reflect on design decisions and production considerations

- Submission includes a written reflection of 200–400 words.
- Reflection names a specific tool or integration from the project and explains why an implementation choice was made.
- Reflection describes a concrete challenge encountered during the project and the steps taken to resolve it.
- Reflection discusses at least one production consideration (e.g., scalability, cost, security, monitoring) with a specific example of how it applies to this agent.

## Monitoring & Logs

CloudWatch log group for the deployed `legacy_cs` runtime:

```sh
/aws/bedrock-agentcore/runtimes/legacy_cs-wf1J24Ch5y-DEFAULT
```

Tail logs with:

```sh
aws logs tail /aws/bedrock-agentcore/runtimes/legacy_cs-wf1J24Ch5y-DEFAULT --log-stream-name-prefix "2026/09/12/[runtime-logs" --follow
aws logs tail /aws/bedrock-agentcore/runtimes/legacy_cs-wf1J24Ch5y-DEFAULT --log-stream-name-prefix "2026/09/12/[runtime-logs" --since 1h
```

GenAI Observability Dashboard:
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#gen-ai-observability/agent-core

Note: observability data may take up to 10 minutes to appear after first launch.
