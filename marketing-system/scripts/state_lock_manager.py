"""State lock manager — prevents concurrent workflows on the same product."""

import json
import os
import time
from datetime import datetime
from pathlib import Path

PRODUCTS_DIR = Path("/home/robotin/.openclaw/products")
STALE_LOCK_SECONDS = 3600  # 1 hour


def acquire_lock(product_id: str, workflow: str) -> bool:
    """Acquire lock for a product. Returns True if acquired, False if already locked."""
    lock_path = PRODUCTS_DIR / product_id / "runtime" / "runtime.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        lock_data = json.loads(lock_path.read_text())
        lock_age = time.time() - lock_data.get("timestamp", 0)

        if lock_age > STALE_LOCK_SECONDS:
            print(f"WARNING: Stale lock detected ({lock_age:.0f}s old, workflow: {lock_data.get('workflow')}). Cleaning up.")
            lock_path.unlink()
        else:
            return False

    lock_data = {
        "workflow": workflow,
        "product_id": product_id,
        "pid": os.getpid(),
        "timestamp": time.time(),
        "acquired_at": datetime.now().isoformat(),
    }
    lock_path.write_text(json.dumps(lock_data, indent=2))
    return True


def release_lock(product_id: str) -> bool:
    """Release lock for a product. Returns True if released."""
    lock_path = PRODUCTS_DIR / product_id / "runtime" / "runtime.lock"
    if lock_path.exists():
        lock_path.unlink()
        return True
    return False


def get_lock_info(product_id: str) -> dict | None:
    """Get current lock info, or None if unlocked."""
    lock_path = PRODUCTS_DIR / product_id / "runtime" / "runtime.lock"
    if lock_path.exists():
        return json.loads(lock_path.read_text())
    return None


def is_locked(product_id: str) -> bool:
    """Check if product is locked (excluding stale locks)."""
    lock_path = PRODUCTS_DIR / product_id / "runtime" / "runtime.lock"
    if not lock_path.exists():
        return False
    lock_data = json.loads(lock_path.read_text())
    lock_age = time.time() - lock_data.get("timestamp", 0)
    if lock_age > STALE_LOCK_SECONDS:
        return False
    return True
