"""Gate handler — manages human gates via Telegram for the marketing system.

Gates are decision points where the system pauses and waits for human approval.
In v1, gates are fire-and-forget: send summary to Telegram, persist state,
and resume when commanded via /strategy approve or /marketing approve.
"""

import json
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")


def create_gate(product_id: str, gate_name: str, gate_type: str,
                summary: str, artifact_paths: list[str] = None,
                run_id: str = None) -> dict:
    """Create a gate record and persist it to runtime_state.

    gate_type: "strategy" | "marketing" | "growth"
    gate_name: "S1" | "S2" | "M1" | "M2" | "M3" | "growth_review"
    """
    gate = {
        "gate_name": gate_name,
        "gate_type": gate_type,
        "product_id": product_id,
        "run_id": run_id,
        "status": "pending",
        "summary": summary,
        "artifact_paths": artifact_paths or [],
        "created_at": datetime.now().isoformat(),
        "decided_at": None,
        "decision": None,
        "decided_by": None,
        "adjustments": None,
    }

    # Persist to runtime_state
    state = _load_runtime_state(product_id)
    state.setdefault("pending_gates", {})[gate_name] = gate
    state["last_gate"] = gate_name
    state["last_updated"] = datetime.now().isoformat()
    _save_runtime_state(product_id, state)

    return gate


def resolve_gate(product_id: str, gate_name: str, decision: str,
                 decided_by: str = "human", adjustments: dict = None) -> dict:
    """Resolve a pending gate with a decision.

    decision: "approved" | "rejected" | "adjust"
    """
    state = _load_runtime_state(product_id)
    gates = state.get("pending_gates", {})

    if gate_name not in gates:
        raise ValueError(f"Gate {gate_name} not found or already resolved")

    gate = gates[gate_name]
    gate["status"] = decision
    gate["decision"] = decision
    gate["decided_at"] = datetime.now().isoformat()
    gate["decided_by"] = decided_by
    if adjustments:
        gate["adjustments"] = adjustments

    # Move from pending to resolved
    state.setdefault("resolved_gates", {})[gate_name] = gate
    del gates[gate_name]
    state["last_updated"] = datetime.now().isoformat()
    _save_runtime_state(product_id, state)

    return gate


def get_pending_gates(product_id: str) -> dict:
    """Get all pending gates for a product."""
    state = _load_runtime_state(product_id)
    return state.get("pending_gates", {})


def format_strategy_gate_s1(product_id: str, market_analysis: dict, buyer_persona: dict) -> str:
    """Format Gate S1 summary for Telegram."""
    avatar = buyer_persona.get("avatar", {})
    pain_points = buyer_persona.get("pain_points", [])[:3]
    competitors = market_analysis.get("competitors", [])[:3]

    lines = [
        f"✅ Strategy v1 — Gate S1",
        f"Producto: {product_id}",
        "",
        "Buyer Persona:",
        f"  {avatar.get('name', '?')}, {avatar.get('age', '?')}, {avatar.get('occupation', '?')}",
        "  Pain points:",
    ]
    for p in pain_points:
        if isinstance(p, str):
            lines.append(f"    - {p}")
        elif isinstance(p, dict):
            lines.append(f"    - {p.get('pain', p.get('description', str(p)))}")

    lines += ["", "Competidores:"]
    for c in competitors:
        if isinstance(c, str):
            lines.append(f"  - {c}")
        elif isinstance(c, dict):
            lines.append(f"  - {c.get('name', '?')}: {c.get('strength', '')}")

    lines += [
        "",
        "Decisión:",
        f"1. /strategy approve {product_id}",
        f"2. /strategy reject {product_id}",
    ]
    return "\n".join(lines)


def format_strategy_gate_s2(product_id: str, brand: dict, seo: dict, channels: dict) -> str:
    """Format Gate S2 summary for Telegram."""
    vp = brand.get("value_proposition", "?")
    channel_list = channels.get("channels", [])
    kw_groups = seo.get("keyword_groups", [])

    lines = [
        f"✅ Strategy completa — Gate S2",
        f"Producto: {product_id}",
        "",
        f"Value Proposition: {vp if isinstance(vp, str) else json.dumps(vp)[:200]}",
        "",
        "Canales:",
    ]
    for ch in channel_list[:5]:
        if isinstance(ch, str):
            lines.append(f"  - {ch}")
        elif isinstance(ch, dict):
            lines.append(f"  - {ch.get('name', '?')}: {ch.get('priority', '')}")

    lines += [
        "",
        f"SEO: {len(kw_groups)} keyword groups",
        "",
        "Decisión:",
        f"1. /strategy approve {product_id}",
        f"2. /strategy reject {product_id}",
    ]
    return "\n".join(lines)


def _load_runtime_state(product_id: str) -> dict:
    path = PRODUCTS_DIR / product_id / "runtime" / "runtime_state.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"product_id": product_id, "pending_gates": {}, "resolved_gates": {}}


def _save_runtime_state(product_id: str, state: dict):
    path = PRODUCTS_DIR / product_id / "runtime" / "runtime_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
