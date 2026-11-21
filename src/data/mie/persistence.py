"""Safe versioned local storage for normalized MIE evidence bundles."""

from __future__ import annotations

import calendar
import json
import math
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.data.mie.models import SCHEMA_VERSION, EvidenceBundle

SECRET_KEYS = re.compile(r"(?:key|token|secret|password|subscription|authorization)", re.I)
RETENTION_MONTHS = {"normalized_data": 24, "evidence_bundle": 60,
                    "retrieval_manifest": 60}


def _safe_url(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not SECRET_KEYS.search(key)]
    return urlunsplit((parts.scheme, host, parts.path, urlencode(query), ""))


def sanitize(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if SECRET_KEYS.search(str(key))
                      else sanitize(item)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return _safe_url(value)
    return value


def save_bundle(bundle: EvidenceBundle, directory: Path | str) -> Path:
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", bundle.bundle_id)
    target = target_dir / f"{safe_id}.json"
    payload = sanitize(bundle.to_dict())
    fd, temp_name = tempfile.mkstemp(prefix=f".{safe_id}-", suffix=".tmp", dir=target_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True,
                      allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return target


def load_bundle(path: Path | str) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported MIE evidence bundle schema version")
    return payload


def freshness(path: Path | str, now: datetime | None = None) -> dict[str, Any]:
    payload = load_bundle(path)
    retrieved_at = datetime.fromisoformat(payload["retrieved_at"])
    current = now or datetime.now(UTC)
    age_days = max(0, (current - retrieved_at).total_seconds() / 86400)
    return {"retrieved_at": payload["retrieved_at"], "age_days": age_days,
            "refresh_due": age_days >= 90}


def retention_due(retrieved_at: datetime, artifact_type: str,
                  now: datetime | None = None) -> bool:
    """Report whether an artifact has reached its approved retention period; never deletes."""
    if artifact_type not in RETENTION_MONTHS:
        raise ValueError(f"Unknown artifact type: {artifact_type}")
    current = now or datetime.now(UTC)
    months = RETENTION_MONTHS[artifact_type]
    month_index = retrieved_at.year * 12 + retrieved_at.month - 1 + months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(retrieved_at.day, calendar.monthrange(year, month)[1])
    deadline = retrieved_at.replace(year=year, month=month, day=day)
    return current >= deadline
