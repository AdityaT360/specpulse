import re
from typing import Any

from app.db.models import Endpoint, TestCase


class TestCaseGenerationError(ValueError):
    pass


def generate_test_case(endpoint: Endpoint, document: dict[str, Any]) -> TestCase:
    path_params: dict[str, Any] = {}
    query_params: dict[str, Any] = {}
    headers: dict[str, Any] = {}

    for raw_parameter in endpoint.parameters:
        parameter = _resolve(raw_parameter, document)
        name = parameter.get("name")
        location = parameter.get("in")
        if not isinstance(name, str) or not isinstance(location, str):
            raise TestCaseGenerationError(
                f"Invalid parameter in {endpoint.method} {endpoint.path}."
            )
        if location != "path" and not parameter.get("required", False):
            continue
        schema = parameter.get("schema")
        if not isinstance(schema, dict):
            raise TestCaseGenerationError(f"Parameter {name} needs a schema.")
        value = _sample(schema, document)
        if isinstance(value, (dict, list)):
            raise TestCaseGenerationError(f"Complex parameter {name} is not supported yet.")
        target = {"path": path_params, "query": query_params, "header": headers}.get(location)
        if target is None:
            raise TestCaseGenerationError(f"Required {location} parameter {name} is not supported.")
        target[name] = value

    missing_path_params = set(re.findall(r"\{([^{}]+)\}", endpoint.path)) - path_params.keys()
    if missing_path_params:
        raise TestCaseGenerationError(
            f"Missing path parameter schemas for {endpoint.method} {endpoint.path}: "
            f"{', '.join(sorted(missing_path_params))}."
        )

    payload = None
    if endpoint.request_body is not None:
        body = _resolve(endpoint.request_body, document)
        content = body.get("content", {})
        if not isinstance(content, dict):
            raise TestCaseGenerationError(
                f"Invalid request body for {endpoint.method} {endpoint.path}."
            )
        media = content.get("application/json")
        if media is None and body.get("required", False):
            raise TestCaseGenerationError(
                f"Required JSON body unavailable for {endpoint.method} {endpoint.path}."
            )
        if media is not None:
            if not isinstance(media, dict):
                raise TestCaseGenerationError("Invalid application/json media type.")
            if "example" in media:
                payload = media["example"]
            else:
                schema = media.get("schema")
                if not isinstance(schema, dict):
                    raise TestCaseGenerationError("JSON request body needs a schema or example.")
                payload = _sample(schema, document)
            headers["Content-Type"] = "application/json"

    success_codes = sorted(
        int(code)
        for code in endpoint.responses
        if len(code) == 3 and code.isdigit() and 200 <= int(code) < 300
    )
    return TestCase(
        endpoint_id=endpoint.id,
        name=f"{endpoint.method} {endpoint.path} success"[:255],
        expected_status=success_codes[0] if success_codes else 200,
        path_params=path_params,
        query_params=query_params,
        headers=headers,
        request_payload=payload,
    )


def _resolve(value: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    seen: set[str] = set()
    while "$ref" in value:
        ref = value["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            raise TestCaseGenerationError(f"Unsupported or circular reference: {ref}.")
        seen.add(ref)
        resolved: Any = document
        for part in ref[2:].split("/"):
            key = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(resolved, dict) or key not in resolved:
                raise TestCaseGenerationError(f"Unresolved reference: {ref}.")
            resolved = resolved[key]
        if not isinstance(resolved, dict):
            raise TestCaseGenerationError(f"Reference must point to an object: {ref}.")
        value = resolved
    return value


def _sample(raw_schema: dict[str, Any], document: dict[str, Any], depth: int = 0) -> Any:
    if depth > 12:
        raise TestCaseGenerationError("Schema nesting is too deep.")
    schema = _resolve(raw_schema, document)
    for key in ("example", "default", "const"):
        if key in schema:
            return schema[key]
    if "enum" in schema:
        values = schema["enum"]
        if isinstance(values, list) and values:
            return values[0]
        raise TestCaseGenerationError("A schema enum must contain a value.")

    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((item for item in kind if item != "null"), None)
    if kind == "object" or (kind is None and "properties" in schema):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            raise TestCaseGenerationError("Invalid object schema.")
        result = {}
        for name in required:
            child = properties.get(name)
            if not isinstance(name, str) or not isinstance(child, dict):
                raise TestCaseGenerationError(f"Required property {name} needs a schema.")
            result[name] = _sample(child, document, depth + 1)
        return result
    if kind == "array":
        count = schema.get("minItems", 0)
        if not isinstance(count, int) or count < 0 or count > 10:
            raise TestCaseGenerationError("Unsupported array minItems value.")
        if count == 0:
            return []
        items = schema.get("items")
        if not isinstance(items, dict):
            raise TestCaseGenerationError("Array items need a schema.")
        return [_sample(items, document, depth + 1) for _ in range(count)]
    if kind == "string":
        formats = {
            "email": "sample@example.com",
            "date": "2026-01-01",
            "date-time": "2026-01-01T00:00:00Z",
            "uuid": "00000000-0000-4000-8000-000000000001",
        }
        return formats.get(schema.get("format"), "sample")
    if kind == "integer":
        return 1
    if kind == "number":
        return 1.0
    if kind == "boolean":
        return True
    raise TestCaseGenerationError(f"Unsupported schema type: {kind}.")
