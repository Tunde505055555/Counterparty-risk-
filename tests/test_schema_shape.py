"""Offline structural tests — no node, no network, no LLM.

These encode the rules that previously produced "Could not load contract schema",
so a regression fails here instead of in Studio.
"""

from __future__ import annotations

import ast
import json
import re

from conftest import CONTRACT_PATH

SAFE_PARAM_TYPES = {"str", "u256", "u8", "int", "bool"}


def _tree(source: str) -> ast.Module:
    return ast.parse(source)


def _contract_class(source: str) -> ast.ClassDef:
    for node in _tree(source).body:
        if isinstance(node, ast.ClassDef) and any(
            ast.unparse(b) == "gl.Contract" for b in node.bases
        ):
            return node
    raise AssertionError("no class inheriting gl.Contract found")


def test_version_and_depends_header(contract_source: str) -> None:
    lines = contract_source.splitlines()
    assert re.fullmatch(r"# v\d+\.\d+\.\d+", lines[0].strip()), lines[0]
    assert lines[0].strip() == "# v0.2.16"
    header = json.loads(lines[1].lstrip("# ").strip())
    assert header["Depends"].startswith("py-genlayer:")


def test_inherits_gl_contract_without_decorator(contract_source: str) -> None:
    cls = _contract_class(contract_source)
    assert cls.name == "CounterpartyRisk"
    assert "gl.contract" not in {ast.unparse(d) for d in cls.decorator_list}


def test_stored_dataclass_has_no_nested_collections(contract_source: str) -> None:
    for node in _tree(contract_source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        if "allow_storage" not in {ast.unparse(d) for d in node.decorator_list}:
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign):
                ann = ast.unparse(stmt.annotation)
                assert "[" not in ann, f"{node.name}.{ast.unparse(stmt.target)}: {ann}"


def test_public_signatures_are_schema_safe(contract_source: str) -> None:
    cls = _contract_class(contract_source)
    seen = 0
    for stmt in cls.body:
        if not isinstance(stmt, ast.FunctionDef):
            continue
        decs = {ast.unparse(d) for d in stmt.decorator_list}
        if not decs & {"gl.public.write", "gl.public.view"}:
            continue
        seen += 1
        for arg in stmt.args.args[1:]:
            assert arg.annotation is not None, f"{stmt.name}({arg.arg})"
            assert ast.unparse(arg.annotation) in SAFE_PARAM_TYPES, (
                f"{stmt.name}({arg.arg}: {ast.unparse(arg.annotation)})"
            )
    assert seen >= 10


def test_expected_public_surface(contract_source: str) -> None:
    cls = _contract_class(contract_source)
    names = {
        s.name
        for s in cls.body
        if isinstance(s, ast.FunctionDef)
        and {ast.unparse(d) for d in s.decorator_list} & {"gl.public.write", "gl.public.view"}
    }
    assert {
        "set_allowed_domains",
        "open_case",
        "submit_evidence",
        "assess",
        "challenge",
        "reviewer_ruling",
        "request_finalize",
        "finalize",
        "config",
        "get_case",
        "get_assessment",
        "get_rulings",
        "cases_of",
    } <= names


def test_consensus_tiers_are_monotonically_stricter(contract_source: str) -> None:
    src = CONTRACT_PATH.read_text(encoding="utf-8")
    tolerances = json.loads(
        re.search(r"SCORE_TOLERANCE_BY_ROUND = (\[[^\]]*\])", src).group(1)
    )
    assert tolerances == sorted(tolerances, reverse=True)
    assert tolerances[-1] == 0, "the final round must demand exact numeric agreement"
    assert len(tolerances) >= 2


def test_consensus_patterns_present(contract_source: str) -> None:
    for pattern in (
        "gl.eq_principle.strict_eq",
        "gl.vm.run_nondet_unsafe",
        "gl.nondet.exec_prompt",
        "gl.nondet.web.render",
    ):
        assert pattern in contract_source, pattern


def test_insufficient_evidence_is_off_the_risk_axis(contract_source: str) -> None:
    names = json.loads(
        re.search(r"RISK_LEVEL_NAMES = (\[[^\]]*\])", contract_source)
        .group(1)
        .replace("'", '"')
    )
    assert names == ["LOW", "MEDIUM", "HIGH", "CRITICAL", "INSUFFICIENT_EVIDENCE"]
    assert names[-1] == "INSUFFICIENT_EVIDENCE"


def test_examples_match_the_open_case_signature(contract_source: str, examples: dict) -> None:
    cls = _contract_class(contract_source)
    open_case = next(
        s for s in cls.body if isinstance(s, ast.FunctionDef) and s.name == "open_case"
    )
    params = [a.arg for a in open_case.args.args[1:]]
    assert examples, "no example payloads found"
    for name, payload in examples.items():
        assert set(payload["open_case"]) == set(params), name
        json.loads(payload["open_case"]["criteria"])
        json.loads(payload["open_case"]["evidence_urls"])
        json.loads(payload["constructor"]["allowed_domains"])


def test_settlement_paths_are_authorized(contract_source: str) -> None:
    """challenge / request_finalize / finalize must all gate on the case parties,
    and finalize must require assent from a second party."""
    cls = _contract_class(contract_source)
    bodies = {
        s.name: ast.unparse(s)
        for s in cls.body
        if isinstance(s, ast.FunctionDef)
    }
    for name in ("challenge", "request_finalize", "finalize"):
        assert "_require_party" in bodies[name], name
    assert "already consumed its challenge" in bodies["challenge"]
    assert "finalize_request" in bodies["finalize"]
    assert "_require_party" in bodies
    assert "case.requester" in bodies["_require_party"]
    assert "case.reviewer" in bodies["_require_party"]


def test_score_level_invariant_is_shared(contract_source: str) -> None:
    """The reviewer settlement path and the network ruling path must apply the
    same score->level mapping helper — no second, divergent implementation."""
    cls = _contract_class(contract_source)
    bodies = {
        s.name: ast.unparse(s)
        for s in cls.body
        if isinstance(s, ast.FunctionDef)
    }
    assert "_enforce_score_level" in bodies
    assert "_enforce_score_level" in bodies["reviewer_ruling"]
    assert "_enforce_score_level" in bodies["_normalize_ruling"]
    assert "_level_for_score" not in bodies["reviewer_ruling"]
    assert "_level_for_score" in bodies["_enforce_score_level"]
