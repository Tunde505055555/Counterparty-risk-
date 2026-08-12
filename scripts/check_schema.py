"""Static sanity checks on contracts/counterparty_risk.py.

Runs offline. It does not import genlayer — it parses the source and asserts the
structural rules that cause "Could not load contract schema" in Studio:

  * the version and Depends header lines are present and first
  * exactly one class, inheriting gl.Contract (no @gl.contract decorator)
  * public method signatures use only schema-safe parameter types
  * no nested storage collections inside a stored dataclass

Usage:  python scripts/check_schema.py [path]
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

SAFE_PARAM_TYPES = {"str", "u256", "u8", "int", "bool"}
CONTRACT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("contracts/counterparty_risk.py")

problems: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def ok(msg: str) -> None:
    notes.append(msg)


source = CONTRACT.read_text(encoding="utf-8")
lines = source.splitlines()

# --- header -------------------------------------------------------------------
if not lines or not re.fullmatch(r"# v\d+\.\d+\.\d+", lines[0].strip()):
    fail("line 1 must be a version comment, e.g. '# v0.2.16'")
else:
    ok(f"version header {lines[0].strip()}")

if len(lines) < 2 or '"Depends"' not in lines[1]:
    fail("line 2 must be the Depends comment with the py-genlayer hash")
else:
    ok("Depends header present")

# --- AST ----------------------------------------------------------------------
tree = ast.parse(source)
classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
contracts = [c for c in classes if any(ast.unparse(b) == "gl.Contract" for b in c.bases)]

if len(contracts) != 1:
    fail(f"expected exactly one class inheriting gl.Contract, found {len(contracts)}")
else:
    ok(f"contract class: {contracts[0].name}(gl.Contract)")

for c in classes:
    for dec in c.decorator_list:
        if ast.unparse(dec) == "gl.contract":
            fail(f"@gl.contract is not valid in v0.2.16 (on class {c.name})")

# stored dataclasses must hold primitives only
for c in classes:
    decs = {ast.unparse(d) for d in c.decorator_list}
    if "allow_storage" not in decs:
        continue
    for stmt in c.body:
        if isinstance(stmt, ast.AnnAssign):
            ann = ast.unparse(stmt.annotation)
            if "[" in ann:
                fail(
                    f"{c.name}.{ast.unparse(stmt.target)}: nested collection '{ann}' "
                    "inside a stored dataclass breaks the schema"
                )
    ok(f"stored dataclass {c.name} holds primitives only")

# public method signatures
if contracts:
    public = 0
    for stmt in contracts[0].body:
        if not isinstance(stmt, ast.FunctionDef):
            continue
        decs = {ast.unparse(d) for d in stmt.decorator_list}
        if not decs & {"gl.public.write", "gl.public.view", "gl.public.write.payable"}:
            continue
        public += 1
        for arg in stmt.args.args:
            if arg.arg == "self":
                continue
            if arg.annotation is None:
                fail(f"{stmt.name}({arg.arg}) is missing a type annotation")
            elif ast.unparse(arg.annotation) not in SAFE_PARAM_TYPES:
                fail(
                    f"{stmt.name}({arg.arg}: {ast.unparse(arg.annotation)}) "
                    "uses a parameter type that is not schema-safe; "
                    f"use one of {sorted(SAFE_PARAM_TYPES)} and pass lists as JSON strings"
                )
    ok(f"{public} public methods checked")

# --- report -------------------------------------------------------------------
for n in notes:
    print(f"  ok   {n}")
for p in problems:
    print(f"  FAIL {p}")

print()
if problems:
    print(f"{len(problems)} problem(s) found in {CONTRACT}")
    sys.exit(1)
print(f"{CONTRACT} passes the schema sanity checks")
