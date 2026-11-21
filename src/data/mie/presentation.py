"""Plain evidence summaries. This module intentionally exposes no scoring API."""

from src.data.mie.models import EvidenceBundle


def render_evidence(bundle: EvidenceBundle) -> str:
    lines = [f"MIE evidence bundle {bundle.bundle_id} (schema {bundle.schema_version})",
             f"Retrieved: {bundle.retrieved_at}", "", "Retrieval coverage:"]
    for retrieval in bundle.retrievals:
        missing = ", ".join(retrieval.missing_periods) or "none"
        lines.append(f"- {retrieval.source_id}: {retrieval.status}; "
                     f"source mode {retrieval.source_mode}; records {retrieval.record_count}; "
                     f"missing {missing}")
        lines.extend(f"  Caveat: {warning}" for warning in retrieval.warnings)
    lines.extend(["", "Observations:"])
    if not bundle.observations:
        lines.append("- No valid observations returned; absence is not zero.")
    for observation in bundle.observations:
        lines.append(f"- FACT | {observation.indicator_id} | {observation.period} | "
                     f"{observation.value!s} {observation.unit} | "
                     f"{observation.geography} | {observation.source_mode} | "
                     f"{observation.source_url}")
    if bundle.interpretations:
        lines.extend(["", "Human interpretations:"])
        lines.extend(f"- INTERPRETATION | {item.get('text', '')}" for item in bundle.interpretations)
    return "\n".join(lines)
