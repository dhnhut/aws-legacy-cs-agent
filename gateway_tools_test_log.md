# Gateway / MCP Tool Test Log

Local test runs of the agent after wiring `MCPClient` to the AgentCore Gateway
(`GATEWAY_URL` in `main.py`). Each run below exercises a distinct
Gateway-backed target and shows a successful, well-formed (non-empty,
non-error) tool result surfaced in the agent's final answer.

## Test 1 — API-based target (`order-tracker`, API Gateway)

Command:
```
uv run src/customer_support_agent/main.py '{"prompt": "What is the status of order ORD-001?", "actor_id": "CUST-123", "session_id": "test-session-1"}'
```

Output:
```
Tool #1: order-tracker___get_order
Your order **ORD-001** is **SHIPPED** and on its way to you! 📦

**Order Details:**
- **Product:** Wireless Headphones Pro
- **Total:** $89.99
- **Carrier:** UPS
- **Tracking Number:** TRK987654321
- **Estimated Delivery:** September 14, 2026

You can track the package using the provided tracking number with UPS to see its current location and delivery progress.
```

## Test 2 — Lambda-based target (`refund-processor`, Lambda)

Command:
```
uv run src/customer_support_agent/main.py '{"prompt": "I received order ORD-001 damaged, please initiate a refund for the full $89.99.", "actor_id": "CUST-123", "session_id": "test-session-2"}'
```

Output:
```
Tool #1: refund-processor___initiate_refund
Perfect! Your refund has been approved.

**Refund Details:**
- **Refund ID:** REF-J108SPIN
- **Order:** ORD-001
- **Amount:** $89.99
- **Status:** APPROVED
- **Credit Timeline:** Will appear in your account in 3-5 business days

The refund was processed for the damaged item you received. If you have any further questions or need assistance with anything else, I'm here to help!
```

## Result

Both distinct Gateway-backed tools (`order-tracker___get_order` — API Gateway
target, `refund-processor___initiate_refund` — Lambda target) were invoked
successfully via `MCPClient`, each returning a well-formed, non-empty result
that the agent incorporated into its response.
