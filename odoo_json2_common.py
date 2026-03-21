#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.parse
import urllib.request


def env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def optional_env(name, default=None):
    return os.environ.get(name, default)


def parse_json(value, default):
    if value is None:
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON for argument: {exc}") from exc
    return parsed


def parse_json_input(json_value=None, file_path=None, default=None):
    if json_value is not None and file_path is not None:
        raise RuntimeError("Use either inline JSON or a JSON file/stdin source, not both.")
    if file_path is not None:
        if file_path == "-":
            raw_value = os.sys.stdin.read()
        else:
            with open(file_path, "r", encoding="utf-8") as handle:
                raw_value = handle.read()
        return parse_json(raw_value, default)
    return parse_json(json_value, default)


def request_json(url, api_key, db_name, payload=None):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-Odoo-Database": db_name,
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, headers=headers, data=data)
    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = body
        else:
            parsed = None
        raise RuntimeError(
            json.dumps(
                {
                    "status": exc.code,
                    "reason": exc.reason,
                    "body": parsed,
                },
                indent=2,
                ensure_ascii=True,
            )
        ) from exc


def build_agent_context(raw_context, channel):
    context = dict(raw_context)
    context["agent_mode"] = True
    context["agent_channel"] = channel
    return context


def issue_confirmation_token(base_url, api_key, db_name, model, method, ids):
    url = f"{base_url.rstrip('/')}/json/2/strictbase.agent.confirmation/issue_token"
    payload = {
        "model_name": model,
        "method_name": method,
        "record_ids": ids or [],
    }
    return request_json(url, api_key, db_name, payload=payload)


def call_json2(base_url, db_name, api_key, model, method, *, ids=None, data=None, context=None, confirm_outbound=False):
    payload = dict(data or {})
    if ids:
        payload["ids"] = list(ids)

    agent_context = build_agent_context(context or {}, channel=(context or {}).get("agent_channel", "mcp"))
    if confirm_outbound:
        approver_api_key = optional_env("ODOO_APPROVER_API_KEY")
        if not approver_api_key:
            raise RuntimeError(
                "Outbound confirmation requires ODOO_APPROVER_API_KEY. "
                "The agent API key may not issue its own confirmation tokens."
            )
        agent_context["agent_confirmation_token"] = issue_confirmation_token(
            base_url=base_url,
            api_key=approver_api_key,
            db_name=db_name,
            model=model,
            method=method,
            ids=ids or [],
        )
    payload["context"] = agent_context

    url = f"{base_url.rstrip('/')}/json/2/{model}/{method}"
    return request_json(url, api_key, db_name, payload=payload)


def doc_index(base_url, db_name, api_key):
    url = f"{base_url.rstrip('/')}/doc-bearer/index.json"
    return request_json(url, api_key, db_name)


def doc_model(base_url, db_name, api_key, model):
    model_name = urllib.parse.quote(model, safe=".")
    url = f"{base_url.rstrip('/')}/doc-bearer/{model_name}.json"
    return request_json(url, api_key, db_name)
