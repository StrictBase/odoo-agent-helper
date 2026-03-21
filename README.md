# Odoo Agent Helper

Thin local helper for Odoo 19 JSON-2 agent-mode calls.

It keeps the interface generic:

- `exec-spec` for stable file-driven execution through a fixed shell command
- `call` for arbitrary model/method execution
- `search-read`, `read`, `create`, and `write` as generic convenience wrappers for common methods
- `schema-summary` for compact cached model summaries
- `lookup` for cached partner/project/task/employee lookup
- `doc-index` for global introspection
- `doc-model` for model-specific introspection

It automatically injects:

- `agent_mode = true`
- `agent_channel = "cli"`

It optionally injects:

- a one-time scoped `agent_confirmation_token`

Environment variables:

- `ODOO_BASE_URL`
- `ODOO_DB`
- `ODOO_API_KEY`
- `ODOO_APPROVER_API_KEY`
  - optional
  - required only when using `--confirm-outbound`
  - must belong to a user in the `Agent Confirmation Approver` group

Wrapper config:

- copy `odoo_local.env-dist` to `odoo_local.env`
- copy `odoo_erp.env-dist` to `odoo_erp.env`
- keep `odoo_local.env` out of Git
- keep `odoo_erp.env` out of Git
- alternatively set the variables directly in the shell environment

Example:

```bash
cp odoo_local.env-dist odoo_local.env
cp odoo_erp.env-dist odoo_erp.env

export ODOO_BASE_URL='http://127.0.0.1:16069'
export ODOO_DB='strictbase'
export ODOO_API_KEY='...'

python3 odoo_json2.py doc-model project.task
python3 odoo_json2.py exec-spec /tmp/codex_odoo_request.json --pretty
python3 odoo_json2.py schema-summary project.task --pretty
python3 odoo_json2.py schema-summary project.project --field pricing_type --field sale_line_id --field partner_id --field allow_timesheets --pretty
python3 odoo_json2.py lookup project T4B --pretty
python3 odoo_json2.py call res.partner search --data-json '{"domain": [["id", "=", 1]]}'
python3 odoo_json2.py search-read project.task --domain-json '[["project_id", "=", 18]]' --fields-json '["id", "name"]' --pretty
python3 odoo_json2.py create project.task --vals-json '{"name": "Nikki'\''s layout issue", "project_id": 18}' --pretty
printf '%s\n' '[{"name":"Task A","project_id":23},{"name":"Task B","project_id":23}]' | \
  python3 odoo_json2.py create project.task --vals-list-file - --pretty
python3 odoo_json2.py write project.task --ids 40 --vals-json '{"name": "Updated task title"}' --pretty
python3 odoo_json2.py call res.partner message_post --ids 338 --confirm-outbound --data-json '{"body": "Approved send", "message_type": "comment", "subtype_xmlid": "mail.mt_comment", "partner_ids": [338]}'
```

For more reliable quoting, any JSON-bearing option can be sourced from a file or stdin:

```bash
printf '%s\n' '{"name":"Nikki'\''s layout issue","project_id":18}' | \
  python3 odoo_json2.py create project.task --vals-file -
```

The helper stores schema and lookup caches on disk under `.cache/`.
That cache is for execution speed only. It does not need to be loaded into the active Codex conversation unless Odoo work is actually requested.

Preferred stable execution path for Codex:

1. Write a JSON spec to `/tmp/codex_odoo_request.json`
2. Run:

```bash
./odoo_local.sh exec-spec
```

Production wrapper:

```bash
./odoo_erp.sh exec-spec
```

Important:

- `--confirm-outbound` no longer uses the same agent API key to mint a confirmation token.
- it requires `ODOO_APPROVER_API_KEY`
- the approver key must belong to a separate trusted user in the `Agent Confirmation Approver` group
- this is intentional, so the agent cannot self-authorize outbound actions
- if Codex can freely read `ODOO_APPROVER_API_KEY` from the host environment or env file, then the trust boundary moves to the host and you no longer have true human confirmation
- for a real approval boundary, keep `ODOO_APPROVER_API_KEY` out of the agent's normal runtime and provide it only through a separate trusted confirmation step

Example spec:

```json
{
  "action": "lookup",
  "kind": "partner",
  "query": "The Learning Hub"
}
```

Example spec for create:

```json
{
  "action": "create",
  "model": "project.task",
  "vals": {
    "name": "Nikki's layout issue",
    "project_id": 18
  }
}
```

For recurring tasks, prefer:

- `exec-spec` with the fixed `/tmp/codex_odoo_request.json` path for low-friction execution
- `schema-summary --field ...` or `schema-summary --contains ...`
- `lookup ...`
- one batch `create --vals-list-file -` when creating several sibling records

instead of piping full `doc-model` output through shell filters such as `rg`.
