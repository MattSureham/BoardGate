"""Restricted YAML/JSON loading for manufacturing rule profiles."""

from __future__ import annotations

import json
import re
from collections.abc import Hashable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.tokens import AliasToken, AnchorToken, TagToken

from boardgate.config.models import RuleProfile

MAX_PROFILE_BYTES = 1024 * 1024
_JSON_SUFFIXES = {".json"}
_YAML_SUFFIXES = {".yaml", ".yml"}


class RuleProfileError(ValueError):
    """Typed, source-safe configuration failure."""

    def __init__(self, code: str, source: str, detail: str) -> None:
        self.code = code
        self.source = source
        self.detail = detail
        super().__init__(f"{code}: {detail} [{source}]")


class _RestrictedLoader(yaml.SafeLoader):
    """SafeLoader variant with deterministic scalar and mapping behavior."""


_RestrictedLoader.yaml_implicit_resolvers = deepcopy(
    yaml.SafeLoader.yaml_implicit_resolvers
)
for _resolver_key, _resolvers in list(
    _RestrictedLoader.yaml_implicit_resolvers.items()
):
    _RestrictedLoader.yaml_implicit_resolvers[_resolver_key] = [
        resolver for resolver in _resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
_RestrictedLoader.add_implicit_resolver(  # type: ignore[no-untyped-call]
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _construct_unique_mapping(
    loader: _RestrictedLoader,
    node: MappingNode,
    deep: bool = False,
) -> Mapping[Hashable, Any]:
    """Construct a mapping while rejecting duplicate keys."""
    loader.flatten_mapping(node)
    result: dict[Hashable, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, Hashable):
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "found an unhashable key",
                key_node.start_mark,
            )
        if key in result:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_RestrictedLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _source_label(path: Path) -> str:
    """Keep diagnostics useful without exposing an absolute host path."""
    return path.name or "<profile>"


def _reject_json_constant(value: str) -> None:
    msg = f"non-finite JSON number {value!r} is not allowed"
    raise ValueError(msg)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            msg = f"duplicate JSON key {key!r}"
            raise ValueError(msg)
        result[key] = value
    return result


def _load_json(text: str, source: str) -> Mapping[str, Any]:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as error:
        detail = (
            f"invalid JSON at line {error.lineno}, column {error.colno}"
            if isinstance(error, json.JSONDecodeError)
            else str(error)
        )
        raise RuleProfileError("PROFILE_SYNTAX_ERROR", source, detail) from error
    if not isinstance(value, Mapping):
        raise RuleProfileError(
            "PROFILE_ROOT_ERROR",
            source,
            "profile root must be an object",
        )
    return value


def _load_yaml(text: str, source: str) -> Mapping[str, Any]:
    try:
        for token in yaml.scan(text, Loader=_RestrictedLoader):
            if isinstance(token, (AliasToken, AnchorToken)):
                raise RuleProfileError(
                    "PROFILE_YAML_REFERENCE_REJECTED",
                    source,
                    "YAML anchors and aliases are not allowed",
                )
            if isinstance(token, TagToken):
                raise RuleProfileError(
                    "PROFILE_YAML_TAG_REJECTED",
                    source,
                    "explicit YAML tags are not allowed",
                )
        documents = list(yaml.load_all(text, Loader=_RestrictedLoader))
    except RuleProfileError:
        raise
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = (
            f" at line {mark.line + 1}, column {mark.column + 1}"
            if mark is not None
            else ""
        )
        raise RuleProfileError(
            "PROFILE_SYNTAX_ERROR",
            source,
            f"invalid YAML{location}",
        ) from error
    if len(documents) != 1:
        raise RuleProfileError(
            "PROFILE_DOCUMENT_COUNT",
            source,
            "exactly one YAML document is required",
        )
    value = documents[0]
    if not isinstance(value, Mapping):
        raise RuleProfileError(
            "PROFILE_ROOT_ERROR",
            source,
            "profile root must be a mapping",
        )
    return value


def load_rule_profile_bytes(
    payload: bytes,
    *,
    source: str,
    format_hint: str,
) -> RuleProfile:
    """Validate a bounded profile payload without relying on path state."""
    if len(payload) > MAX_PROFILE_BYTES:
        raise RuleProfileError(
            "PROFILE_TOO_LARGE",
            source,
            f"profile exceeds {MAX_PROFILE_BYTES} bytes",
        )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise RuleProfileError(
            "PROFILE_ENCODING_ERROR",
            source,
            "profile must be UTF-8",
        ) from error
    suffix = format_hint.casefold()
    if suffix in _JSON_SUFFIXES:
        raw = _load_json(text, source)
    elif suffix in _YAML_SUFFIXES:
        raw = _load_yaml(text, source)
    else:
        raise RuleProfileError(
            "PROFILE_FORMAT_ERROR",
            source,
            "profile extension must be .json, .yaml, or .yml",
        )
    try:
        normalized = json.dumps(
            raw,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise RuleProfileError(
            "PROFILE_VALUE_ERROR",
            source,
            "profile contains a non-JSON scalar",
        ) from error
    try:
        return RuleProfile.model_validate_json(normalized)
    except ValidationError as error:
        first = error.errors(include_url=False, include_input=False)[0]
        location = ".".join(str(part) for part in first["loc"]) or "<root>"
        raise RuleProfileError(
            "PROFILE_VALIDATION_ERROR",
            source,
            f"{location}: {first['msg']}",
        ) from error


def load_rule_profile(path: Path) -> RuleProfile:
    """Read and validate a rule profile with bounded, source-safe errors."""
    source = _source_label(path)
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise RuleProfileError(
            "PROFILE_READ_ERROR",
            source,
            "profile could not be read",
        ) from error
    return load_rule_profile_bytes(
        payload,
        source=source,
        format_hint=path.suffix,
    )
