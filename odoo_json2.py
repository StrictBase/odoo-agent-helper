#!/usr/bin/env python3
import argparse
import json
import sys

from odoo_fast_cache import get_schema_summary, lookup_entities
from odoo_json2_common import call_json2, doc_index, doc_model, env, parse_json_input


DEFAULT_EXEC_SPEC_FILE = "/tmp/codex_odoo_request.json"


def print_result(result, pretty):
    print(json.dumps(result, indent=2 if pretty else None, ensure_ascii=True))


def execute_call(args, *, method, data=None):
    base_url = env("ODOO_BASE_URL")
    db_name = env("ODOO_DB")
    api_key = env("ODOO_API_KEY")
    raw_context = parse_json_input(args.context_json, args.context_file, {})
    raw_context["agent_channel"] = args.agent_channel
    try:
        result = call_json2(
            base_url,
            db_name,
            api_key,
            args.model,
            method,
            ids=getattr(args, "ids", []),
            data=data or {},
            context=raw_context,
            confirm_outbound=getattr(args, "confirm_outbound", False),
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print_result(result, args.pretty)


def cmd_call(args):
    data = parse_json_input(args.data_json, args.data_file, {})
    execute_call(args, method=args.method, data=data)


def cmd_search_read(args):
    data = {
        "domain": parse_json_input(args.domain_json, args.domain_file, []),
        "fields": parse_json_input(args.fields_json, args.fields_file, []),
        "limit": args.limit,
        "offset": args.offset,
    }
    if args.order:
        data["order"] = args.order
    execute_call(args, method="search_read", data=data)


def cmd_read(args):
    data = {
        "fields": parse_json_input(args.fields_json, args.fields_file, []),
    }
    execute_call(args, method="read", data=data)


def cmd_create(args):
    vals_list = parse_json_input(args.vals_list_json, args.vals_list_file, None)
    if vals_list is None:
        single_vals = parse_json_input(args.vals_json, args.vals_file, None)
        if single_vals is None:
            raise SystemExit("Provide either --vals-json/--vals-file or --vals-list-json/--vals-list-file.")
        vals_list = [single_vals]
    execute_call(args, method="create", data={"vals_list": vals_list})


def cmd_write(args):
    vals = parse_json_input(args.vals_json, args.vals_file, None)
    if vals is None:
        raise SystemExit("Provide --vals-json or --vals-file.")
    execute_call(args, method="write", data={"vals": vals})


def cmd_doc_index(args):
    try:
        result = doc_index(env("ODOO_BASE_URL"), env("ODOO_DB"), env("ODOO_API_KEY"))
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print_result(result, args.pretty)


def cmd_doc_model(args):
    try:
        result = doc_model(env("ODOO_BASE_URL"), env("ODOO_DB"), env("ODOO_API_KEY"), args.model)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print_result(result, args.pretty)


def cmd_schema_summary(args):
    try:
        result = get_schema_summary(
            env("ODOO_BASE_URL"),
            env("ODOO_DB"),
            env("ODOO_API_KEY"),
            args.model,
            refresh=args.refresh,
            field_names=args.field_names,
            contains_terms=args.contains_terms,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print_result(result, args.pretty)


def cmd_lookup(args):
    try:
        result = lookup_entities(
            env("ODOO_BASE_URL"),
            env("ODOO_DB"),
            env("ODOO_API_KEY"),
            args.kind,
            args.query,
            limit=args.limit,
            refresh=args.refresh,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print_result(result, args.pretty)


def _exec_spec_call(base_url, db_name, api_key, spec):
    return call_json2(
        base_url,
        db_name,
        api_key,
        spec["model"],
        spec["method"],
        ids=spec.get("ids", []),
        data=spec.get("data", {}),
        context=spec.get("context", {}),
        confirm_outbound=spec.get("confirm_outbound", False),
    )


def _exec_spec_search_read(args):
    data = {
        "domain": args.get("domain", []),
        "fields": args.get("fields", []),
        "limit": args.get("limit", 20),
        "offset": args.get("offset", 0),
    }
    if args.get("order"):
        data["order"] = args["order"]
    return data


def _exec_spec_create(args):
    if "vals_list" in args:
        return {"vals_list": args["vals_list"]}
    if "vals" in args:
        return {"vals_list": [args["vals"]]}
    raise RuntimeError("exec-spec create requires 'vals' or 'vals_list'.")


def _exec_spec_write(args):
    if "vals" not in args:
        raise RuntimeError("exec-spec write requires 'vals'.")
    return {"vals": args["vals"]}


def cmd_exec_spec(args):
    spec = parse_json_input(None, args.spec_file, {})
    if not isinstance(spec, dict):
        raise SystemExit("exec-spec JSON must be an object.")
    action = spec.get("action")
    if not action:
        raise SystemExit("exec-spec requires 'action'.")

    base_url = env("ODOO_BASE_URL")
    db_name = env("ODOO_DB")
    api_key = env("ODOO_API_KEY")

    try:
        if action == "lookup":
            result = lookup_entities(
                base_url,
                db_name,
                api_key,
                spec["kind"],
                spec["query"],
                limit=spec.get("limit", 10),
                refresh=spec.get("refresh", False),
            )
        elif action == "schema_summary":
            result = get_schema_summary(
                base_url,
                db_name,
                api_key,
                spec["model"],
                refresh=spec.get("refresh", False),
                field_names=spec.get("fields"),
                contains_terms=spec.get("contains"),
            )
        elif action == "doc_index":
            result = doc_index(base_url, db_name, api_key)
        elif action == "doc_model":
            result = doc_model(base_url, db_name, api_key, spec["model"])
        elif action == "call":
            result = _exec_spec_call(base_url, db_name, api_key, spec)
        elif action == "search_read":
            spec = dict(spec)
            spec["method"] = "search_read"
            spec["data"] = _exec_spec_search_read(spec)
            result = _exec_spec_call(base_url, db_name, api_key, spec)
        elif action == "read":
            spec = dict(spec)
            spec["method"] = "read"
            spec["data"] = {"fields": spec.get("fields", [])}
            result = _exec_spec_call(base_url, db_name, api_key, spec)
        elif action == "create":
            spec = dict(spec)
            spec["method"] = "create"
            spec["data"] = _exec_spec_create(spec)
            result = _exec_spec_call(base_url, db_name, api_key, spec)
        elif action == "write":
            spec = dict(spec)
            spec["method"] = "write"
            spec["data"] = _exec_spec_write(spec)
            result = _exec_spec_call(base_url, db_name, api_key, spec)
        else:
            raise RuntimeError(f"Unsupported exec-spec action: {action}")
    except KeyError as exc:
        raise SystemExit(f"exec-spec missing required key: {exc.args[0]}") from exc
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    print_result(result, args.pretty)


def add_common_output_argument(parser):
    parser.add_argument("--pretty", action="store_true")


def add_common_context_arguments(parser):
    parser.add_argument("--context-json", help="JSON object merged into Odoo context.")
    parser.add_argument("--context-file", help="Read context JSON from a file or '-' for stdin.")
    parser.add_argument("--agent-channel", default="cli")


def add_common_ids_argument(parser):
    parser.add_argument("--ids", nargs="*", type=int, default=[])


def add_common_confirmation_argument(parser):
    parser.add_argument("--confirm-outbound", action="store_true", help="Allow guarded outbound actions.")


def build_parser():
    parser = argparse.ArgumentParser(description="Thin helper for Odoo 19 JSON-2 agent-mode calls.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    call_parser = subparsers.add_parser("call", help="Execute an arbitrary JSON-2 model method.")
    call_parser.add_argument("model")
    call_parser.add_argument("method")
    add_common_ids_argument(call_parser)
    call_parser.add_argument("--data-json", help="JSON object with method keyword arguments.")
    call_parser.add_argument("--data-file", help="Read method keyword-argument JSON from a file or '-' for stdin.")
    add_common_context_arguments(call_parser)
    add_common_confirmation_argument(call_parser)
    add_common_output_argument(call_parser)
    call_parser.set_defaults(func=cmd_call)

    search_read_parser = subparsers.add_parser("search-read", help="Convenience wrapper for search_read.")
    search_read_parser.add_argument("model")
    search_read_parser.add_argument("--domain-json", help="JSON domain list.")
    search_read_parser.add_argument("--domain-file", help="Read domain JSON from a file or '-' for stdin.")
    search_read_parser.add_argument("--fields-json", help="JSON field-name list.")
    search_read_parser.add_argument("--fields-file", help="Read fields JSON from a file or '-' for stdin.")
    search_read_parser.add_argument("--limit", type=int, default=20)
    search_read_parser.add_argument("--offset", type=int, default=0)
    search_read_parser.add_argument("--order")
    add_common_context_arguments(search_read_parser)
    add_common_output_argument(search_read_parser)
    search_read_parser.set_defaults(func=cmd_search_read)

    read_parser = subparsers.add_parser("read", help="Convenience wrapper for read.")
    read_parser.add_argument("model")
    add_common_ids_argument(read_parser)
    read_parser.add_argument("--fields-json", help="JSON field-name list.")
    read_parser.add_argument("--fields-file", help="Read fields JSON from a file or '-' for stdin.")
    add_common_context_arguments(read_parser)
    add_common_output_argument(read_parser)
    read_parser.set_defaults(func=cmd_read)

    create_parser = subparsers.add_parser("create", help="Convenience wrapper for create.")
    create_parser.add_argument("model")
    create_parser.add_argument("--vals-json", help="JSON object for a single record create.")
    create_parser.add_argument("--vals-file", help="Read single-record vals JSON from a file or '-' for stdin.")
    create_parser.add_argument("--vals-list-json", help="JSON list of vals objects for batch create.")
    create_parser.add_argument("--vals-list-file", help="Read batch vals-list JSON from a file or '-' for stdin.")
    add_common_context_arguments(create_parser)
    add_common_output_argument(create_parser)
    create_parser.set_defaults(func=cmd_create)

    write_parser = subparsers.add_parser("write", help="Convenience wrapper for write.")
    write_parser.add_argument("model")
    add_common_ids_argument(write_parser)
    write_parser.add_argument("--vals-json", help="JSON object with fields to update.")
    write_parser.add_argument("--vals-file", help="Read write vals JSON from a file or '-' for stdin.")
    add_common_context_arguments(write_parser)
    add_common_output_argument(write_parser)
    write_parser.set_defaults(func=cmd_write)

    doc_index_parser = subparsers.add_parser("doc-index", help="Fetch /doc-bearer/index.json.")
    add_common_output_argument(doc_index_parser)
    doc_index_parser.set_defaults(func=cmd_doc_index)

    doc_model_parser = subparsers.add_parser("doc-model", help="Fetch /doc-bearer/<model>.json.")
    doc_model_parser.add_argument("model")
    add_common_output_argument(doc_model_parser)
    doc_model_parser.set_defaults(func=cmd_doc_model)

    schema_summary_parser = subparsers.add_parser("schema-summary", help="Fetch a compact cached schema summary.")
    schema_summary_parser.add_argument("model")
    schema_summary_parser.add_argument("--refresh", action="store_true")
    schema_summary_parser.add_argument("--field", dest="field_names", action="append", help="Filter to an exact field name. Repeatable.")
    schema_summary_parser.add_argument("--contains", dest="contains_terms", action="append", help="Filter fields by name or label substring. Repeatable.")
    add_common_output_argument(schema_summary_parser)
    schema_summary_parser.set_defaults(func=cmd_schema_summary)

    lookup_parser = subparsers.add_parser("lookup", help="Lookup common Odoo entities with helper-side cache.")
    lookup_parser.add_argument("kind", choices=["partner", "project", "task", "employee"])
    lookup_parser.add_argument("query")
    lookup_parser.add_argument("--limit", type=int, default=10)
    lookup_parser.add_argument("--refresh", action="store_true")
    add_common_output_argument(lookup_parser)
    lookup_parser.set_defaults(func=cmd_lookup)

    exec_spec_parser = subparsers.add_parser("exec-spec", help="Execute a JSON spec from a stable file path.")
    exec_spec_parser.add_argument("spec_file", nargs="?", default=DEFAULT_EXEC_SPEC_FILE, help=f"Spec file path. Defaults to {DEFAULT_EXEC_SPEC_FILE}.")
    add_common_output_argument(exec_spec_parser)
    exec_spec_parser.set_defaults(func=cmd_exec_spec)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
