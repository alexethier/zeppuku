"""JSON-AST label DSL for search_notes.

Supported operators:
- {"label": "foo"}
- {"and": [expr, ...]}
- {"or": [expr, ...]}
- {"not": expr}
- {"in": ["foo", "bar"]}   # sugar, lowered to {"or": [{"label": ...}, ...]}
"""
from __future__ import annotations

from typing import Any, TypeVar

from .validators import validate_label

LabelExpr = dict[str, Any]
KeyT = TypeVar("KeyT")

MAX_DSL_DEPTH = 20
MAX_DSL_NODES = 500


def normalize_query(query: dict[str, Any]) -> LabelExpr:
    """Validate and normalize a search query into canonical label/and/or/not AST."""
    node_counter = [0]
    return _normalize_node(query, depth=0, node_counter=node_counter)


def _normalize_node(
    node: dict[str, Any],
    *,
    depth: int,
    node_counter: list[int],
) -> LabelExpr:
    if depth > MAX_DSL_DEPTH:
        raise ValueError(f"query exceeds max depth ({MAX_DSL_DEPTH})")
    node_counter[0] += 1
    if node_counter[0] > MAX_DSL_NODES:
        raise ValueError(f"query exceeds max node count ({MAX_DSL_NODES})")

    if not isinstance(node, dict):
        raise ValueError("query expression must be an object")
    if len(node) != 1:
        raise ValueError("query expression must contain exactly one operator key")

    op, value = next(iter(node.items()))

    if op == "label":
        if not isinstance(value, str):
            raise ValueError("label value must be a string")
        return {"label": validate_label(value)}

    if op == "in":
        if not isinstance(value, list) or not value:
            raise ValueError("in operator requires a non-empty array")
        lowered: list[LabelExpr] = []
        for raw in value:
            if not isinstance(raw, str):
                raise ValueError("in operator values must be strings")
            lowered.append({"label": validate_label(raw)})
        if len(lowered) == 1:
            return lowered[0]
        return {"or": lowered}

    if op in ("and", "or"):
        if not isinstance(value, list) or not value:
            raise ValueError(f"{op} operator requires a non-empty array")
        children = [
            _normalize_node(v, depth=depth + 1, node_counter=node_counter) for v in value
        ]
        if len(children) == 1:
            return children[0]
        return {op: children}

    if op == "not":
        if not isinstance(value, dict):
            raise ValueError("not operator requires a single object child")
        return {"not": _normalize_node(value, depth=depth + 1, node_counter=node_counter)}

    raise ValueError(
        f"unsupported operator {op!r}; expected one of "
        "'label', 'and', 'or', 'not', 'in'"
    )


def extract_labels(expr: LabelExpr) -> set[str]:
    """Return all label literals referenced by the normalized expression."""
    if "label" in expr:
        return {str(expr["label"])}
    if "and" in expr:
        out: set[str] = set()
        for child in expr["and"]:
            out.update(extract_labels(child))
        return out
    if "or" in expr:
        out: set[str] = set()
        for child in expr["or"]:
            out.update(extract_labels(child))
        return out
    if "not" in expr:
        return extract_labels(expr["not"])
    return set()


def evaluate_expr(
    expr: LabelExpr,
    *,
    label_hits: dict[str, set[KeyT]],
    universe: set[KeyT],
) -> set[KeyT]:
    """Evaluate a normalized AST into matching note-row-id set."""
    if "label" in expr:
        return set(label_hits.get(str(expr["label"]), set()))
    if "and" in expr:
        children = expr["and"]
        assert children
        out = evaluate_expr(children[0], label_hits=label_hits, universe=universe)
        for child in children[1:]:
            out &= evaluate_expr(child, label_hits=label_hits, universe=universe)
        return out
    if "or" in expr:
        out: set[KeyT] = set()
        for child in expr["or"]:
            out |= evaluate_expr(child, label_hits=label_hits, universe=universe)
        return out
    if "not" in expr:
        return universe - evaluate_expr(expr["not"], label_hits=label_hits, universe=universe)
    return set()
