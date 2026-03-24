#!/usr/bin/env python3
"""
validate_schema.py — Validate a planner artifact against its JSON Schema.

Usage:
  python3 validate_schema.py <slug> <artifact_name>

Example:
  python3 validate_schema.py personal-finance 00_intake_summary

Exit codes:
  0 = PASS
  1 = FAIL
"""

import json
import sys
from pathlib import Path

WORKSPACE = Path("/home/robotin/.openclaw/workspace-meta-planner")


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <slug> <artifact_name>")
        print(f"Example: {sys.argv[0]} personal-finance 00_intake_summary")
        sys.exit(1)

    slug = sys.argv[1]
    artifact_name = sys.argv[2]

    artifact_path = WORKSPACE / "runs" / slug / f"{artifact_name}.json"
    schema_path = WORKSPACE / "schemas" / f"{artifact_name}.schema.json"

    # Check files exist
    if not artifact_path.exists():
        print(f"FAIL: Artifact not found: {artifact_path}")
        sys.exit(1)

    if not schema_path.exists():
        print(f"FAIL: Schema not found: {schema_path}")
        sys.exit(1)

    # Load files
    try:
        with open(artifact_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)
    except json.JSONDecodeError as e:
        print(f"FAIL: Artifact is not valid JSON: {e}")
        sys.exit(1)

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except json.JSONDecodeError as e:
        print(f"FAIL: Schema is not valid JSON: {e}")
        sys.exit(1)

    # Validate
    try:
        import jsonschema
    except ImportError:
        print("ERROR: jsonschema not installed. Run: pip install jsonschema --break-system-packages")
        sys.exit(1)

    errors = list(jsonschema.Draft7Validator(schema).iter_errors(artifact))

    if errors:
        print(f"FAIL: {artifact_name} has {len(errors)} validation error(s):")
        for i, err in enumerate(errors, 1):
            path = " -> ".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
            print(f"  {i}. [{path}] {err.message}")
        sys.exit(1)

    # Special validation for 03_data_flow_map: orphan_outputs must be empty (L-01)
    if artifact_name == "03_data_flow_map":
        orphans = artifact.get("orphan_outputs", [])
        if orphans:
            print(f"FAIL (L-01): orphan_outputs is not empty. {len(orphans)} orphan(s) found:")
            for orphan in orphans:
                print(f"  - {orphan.get('name', '?')}: {orphan.get('reason_discarded', '?')}")
            print("Pipeline cannot proceed with orphan outputs.")
            sys.exit(1)

        missing = artifact.get("missing_required_artifacts", [])
        if missing:
            print(f"FAIL (L-01): missing_required_artifacts is not empty. {len(missing)} missing artifact(s):")
            for m in missing:
                print(f"  - needed by {m.get('needed_by', '?')}: {m.get('description', '?')}")
            print("Pipeline cannot proceed with missing required artifacts.")
            sys.exit(1)

    print(f"PASS: {artifact_name} validates against schema.")
    sys.exit(0)


if __name__ == "__main__":
    main()
