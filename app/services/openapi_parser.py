import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "options", "head", "trace")
ALLOWED_SPEC_EXTENSIONS = {".json", ".yaml", ".yml"}
MAX_SPEC_BYTES = 1024 * 1024


class OpenAPISpecError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedEndpoint:
    path: str
    method: str
    operation_id: str | None
    summary: str | None
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any] | None
    responses: dict[str, Any]


@dataclass(frozen=True)
class ParsedSpec:
    version: str
    document: dict[str, Any]
    endpoints: list[ParsedEndpoint]


def parse_openapi(content: bytes, filename: str) -> ParsedSpec:
    if not content:
        raise OpenAPISpecError("The uploaded file is empty.")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_SPEC_EXTENSIONS:
        raise OpenAPISpecError("Upload a .json, .yaml, or .yml file.")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise OpenAPISpecError("The uploaded file must use UTF-8 encoding.") from exc

    try:
        document = json.loads(text) if extension == ".json" else yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise OpenAPISpecError("The uploaded file is not valid JSON or YAML.") from exc

    try:
        document = json.loads(json.dumps(document, default=_yaml_scalar_to_json))
    except (TypeError, ValueError) as exc:
        raise OpenAPISpecError("The OpenAPI document contains unsupported YAML values.") from exc

    if not isinstance(document, dict):
        raise OpenAPISpecError("The OpenAPI document must be an object.")

    version = document.get("openapi")
    if not isinstance(version, str) or not version.startswith("3."):
        raise OpenAPISpecError("SpecPulse currently supports OpenAPI 3.x documents.")

    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise OpenAPISpecError("The OpenAPI document must contain a paths object.")

    endpoints: list[ParsedEndpoint] = []
    for path, path_item in paths.items():
        if not isinstance(path, str) or not path.startswith("/"):
            raise OpenAPISpecError("Every OpenAPI path must start with '/'.")
        if not isinstance(path_item, dict):
            raise OpenAPISpecError(f"Path item {path} must be an object.")
        if "$ref" in path_item:
            raise OpenAPISpecError(f"Path Item references are not supported yet: {path}.")

        path_parameters = _read_parameters(path_item.get("parameters"), path, document)
        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue
            if not isinstance(operation, dict):
                raise OpenAPISpecError(f"Operation {method.upper()} {path} must be an object.")

            request_body = operation.get("requestBody")
            if request_body is not None and not isinstance(request_body, dict):
                raise OpenAPISpecError(
                    f"requestBody for {method.upper()} {path} must be an object."
                )

            responses = operation.get("responses", {})
            if not isinstance(responses, dict):
                raise OpenAPISpecError(f"Responses for {method.upper()} {path} must be an object.")

            operation_parameters = _read_parameters(operation.get("parameters"), path, document)
            parameters = path_parameters.copy()
            for parameter in operation_parameters:
                key = (parameter.get("name"), parameter.get("in"))
                parameters = [
                    existing
                    for existing in parameters
                    if (existing.get("name"), existing.get("in")) != key
                ]
                parameters.append(parameter)
            endpoints.append(
                ParsedEndpoint(
                    path=path,
                    method=method.upper(),
                    operation_id=_optional_string(operation.get("operationId")),
                    summary=_optional_string(operation.get("summary")),
                    parameters=parameters,
                    request_body=request_body,
                    responses={str(key): value for key, value in responses.items()},
                )
            )

    return ParsedSpec(version=version, document=document, endpoints=endpoints)


def _read_parameters(
    value: Any, path: str, document: dict[str, Any]
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise OpenAPISpecError(f"Parameters for {path} must be a list of objects.")
    parameters = []
    for item in value:
        if "$ref" in item:
            ref = item["$ref"]
            prefix = "#/components/parameters/"
            if not isinstance(ref, str) or not ref.startswith(prefix):
                raise OpenAPISpecError(f"Unsupported parameter reference in {path}: {ref}.")
            name = ref[len(prefix) :].replace("~1", "/").replace("~0", "~")
            components = document.get("components")
            definitions = components.get("parameters") if isinstance(components, dict) else None
            item = definitions.get(name) if isinstance(definitions, dict) else None
            if not isinstance(item, dict) or "$ref" in item:
                raise OpenAPISpecError(f"Unresolved parameter reference in {path}: {ref}.")
        parameters.append(item)
    return parameters


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _yaml_scalar_to_json(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError
