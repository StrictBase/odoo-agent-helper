#!/usr/bin/env python3
import json
import os
import re
import time

from odoo_json2_common import call_json2, doc_model


CACHE_DIR_NAME = ".cache"
SCHEMA_CACHE_FILE = "schema_summaries.json"
LOOKUP_CACHE_FILE = "entity_lookups.json"
SCHEMA_CACHE_TTL_SECONDS = 24 * 60 * 60
LOOKUP_CACHE_TTL_SECONDS = 12 * 60 * 60

CORE_MODEL_FIELDS = {
    "project.project": [
        "name",
        "partner_id",
        "allow_timesheets",
        "pricing_type",
        "sale_line_id",
        "task_ids",
        "analytic_account_id",
    ],
    "project.task": [
        "name",
        "project_id",
        "partner_id",
        "stage_id",
        "sale_line_id",
        "remaining_hours_so",
        "user_ids",
    ],
    "account.analytic.line": [
        "name",
        "date",
        "unit_amount",
        "project_id",
        "task_id",
        "employee_id",
        "user_id",
        "partner_id",
    ],
    "sale.order": [
        "name",
        "partner_id",
        "state",
        "order_line",
        "amount_total",
    ],
    "sale.order.line": [
        "name",
        "order_id",
        "product_id",
        "qty_delivered",
        "remaining_hours",
        "project_id",
    ],
    "res.partner": [
        "name",
        "email",
        "phone",
        "company_type",
        "parent_id",
        "active",
    ],
    "hr.employee": [
        "name",
        "user_id",
        "work_email",
        "company_id",
    ],
}

LOOKUP_SPECS = {
    "partner": {
        "model": "res.partner",
        "fields": ["id", "name", "email", "active", "company_type"],
    },
    "project": {
        "model": "project.project",
        "fields": ["id", "name", "partner_id", "allow_timesheets", "active"],
    },
    "task": {
        "model": "project.task",
        "fields": ["id", "name", "project_id", "partner_id", "active", "stage_id"],
    },
    "employee": {
        "model": "hr.employee",
        "fields": ["id", "name", "user_id", "work_email", "company_id"],
    },
}


def cache_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, CACHE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def cache_path(file_name):
    return os.path.join(cache_dir(), file_name)


def load_cache(file_name):
    path = cache_path(file_name)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {}


def save_cache(file_name, payload):
    path = cache_path(file_name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True, sort_keys=True)


def normalize_query(value):
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


def is_fresh(entry, ttl_seconds):
    fetched_at = entry.get("fetched_at")
    return bool(fetched_at) and (time.time() - fetched_at) < ttl_seconds


def summarize_model_doc(model_name, model_doc):
    fields = model_doc.get("fields", {})
    interesting_names = CORE_MODEL_FIELDS.get(model_name)
    field_names = interesting_names or sorted(fields.keys())
    summary_fields = []
    for field_name in field_names:
        field = fields.get(field_name)
        if not field:
            continue
        summary_fields.append(
            {
                "name": field_name,
                "type": field.get("type"),
                "string": field.get("string"),
                "readonly": field.get("readonly"),
                "required": field.get("required"),
                "relation": field.get("relation"),
                "selection": field.get("selection"),
            }
        )
    return {
        "model": model_name,
        "name": model_doc.get("name"),
        "fields": summary_fields,
    }


def filter_schema_summary(summary, field_names=None, contains_terms=None):
    if not field_names and not contains_terms:
        return summary
    wanted = {name.lower() for name in (field_names or [])}
    terms = [term.lower() for term in (contains_terms or [])]
    filtered = []
    for field in summary["fields"]:
        field_name = field["name"].lower()
        field_string = (field.get("string") or "").lower()
        if wanted and field_name in wanted:
            filtered.append(field)
            continue
        if terms and any(term in field_name or term in field_string for term in terms):
            filtered.append(field)
    return {
        **summary,
        "fields": filtered,
    }


def get_schema_summary(base_url, db_name, api_key, model_name, refresh=False, field_names=None, contains_terms=None):
    cache = load_cache(SCHEMA_CACHE_FILE)
    cached = cache.get(model_name)
    if cached and not refresh and is_fresh(cached, SCHEMA_CACHE_TTL_SECONDS):
        return {"source": "cache", **filter_schema_summary(cached["summary"], field_names, contains_terms)}
    model_doc = doc_model(base_url, db_name, api_key, model_name)
    summary = summarize_model_doc(model_name, model_doc)
    cache[model_name] = {
        "fetched_at": int(time.time()),
        "summary": summary,
    }
    save_cache(SCHEMA_CACHE_FILE, cache)
    return {"source": "live", **filter_schema_summary(summary, field_names, contains_terms)}


def build_lookup_domain(query_text, extra_domain=None):
    domain = [["name", "ilike", query_text]]
    if extra_domain:
        domain.extend(extra_domain)
    return domain


def perform_lookup(base_url, db_name, api_key, kind, query_text, limit=10):
    spec = LOOKUP_SPECS[kind]
    return call_json2(
        base_url,
        db_name,
        api_key,
        spec["model"],
        "search_read",
        data={
            "domain": build_lookup_domain(query_text),
            "fields": spec["fields"],
            "limit": limit,
            "order": "name asc",
        },
        context={"agent_channel": "cli-fast-cache"},
    )


def lookup_entities(base_url, db_name, api_key, kind, query_text, limit=10, refresh=False):
    if kind not in LOOKUP_SPECS:
        raise RuntimeError(f"Unsupported lookup kind: {kind}")
    normalized = normalize_query(query_text)
    cache = load_cache(LOOKUP_CACHE_FILE)
    kind_cache = cache.setdefault(kind, {})
    cached = kind_cache.get(normalized)
    if cached and not refresh and is_fresh(cached, LOOKUP_CACHE_TTL_SECONDS):
        return {
            "source": "cache",
            "kind": kind,
            "query": query_text,
            "results": cached["results"][:limit],
        }
    results = perform_lookup(base_url, db_name, api_key, kind, query_text, limit=limit)
    kind_cache[normalized] = {
        "fetched_at": int(time.time()),
        "results": results,
    }
    cache[kind] = kind_cache
    save_cache(LOOKUP_CACHE_FILE, cache)
    return {
        "source": "live",
        "kind": kind,
        "query": query_text,
        "results": results,
    }
