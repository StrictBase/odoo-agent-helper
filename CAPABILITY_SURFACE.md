# Capability Surface

This helper is intentionally thin.

Its purpose is to give an agent a broad generic capability surface over Odoo 19 JSON-2 without turning the integration into a catalog of workflow-specific tools.

## Principles

- The agent should do most of the intent-to-action mapping.
- The helper should provide transport, introspection, generic execution, and confirmation support.
- Outbound confirmation must use a separate approver identity, not the agent identity itself.
- The helper should not encode business workflows like `log_timesheet` or `create_ticket`.

## Available capabilities

- `doc-index`
  - fetches the model and method index from `/doc-bearer/index.json`
- `doc-model <model>`
  - fetches model-specific fields and methods from `/doc-bearer/<model>.json`
- `call <model> <method>`
  - executes an arbitrary JSON-2 method call

## Agent context behavior

All calls include:

- `agent_mode = true`
- `agent_channel`

Outbound confirmation can be requested with:

- `--confirm-outbound`

This causes the helper to request a scoped one-time confirmation token from Odoo with `ODOO_APPROVER_API_KEY` and then retry the action with that token in context.

## Recommended agent workflow

1. Inspect candidate models with `doc-index` and `doc-model`.
2. Search for candidate records using `search_read`.
3. Read additional fields when necessary.
4. Execute the required create, write, or message methods using `call`.
5. If an outbound action is required, only retry it with explicit approval.

## Anti-patterns

Do not turn this layer into:

- a collection of customer-specific mappings
- a collection of workflow-specific intent handlers
- a tiny allowlist of prebuilt business actions

The point is to keep the surface broad enough for stronger future agents to use directly.
