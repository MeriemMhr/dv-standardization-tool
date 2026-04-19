"""Run-level reporting helpers for batch standardization."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_unknown_alias_summary(events: list[dict[str, Any]], top_n: int = 50) -> dict[str, Any]:
    alias_counts = Counter()
    alias_examples: dict[str, dict[str, str]] = {}
    by_source: dict[str, Counter] = defaultdict(Counter)
    by_dataset_type: dict[str, Counter] = defaultdict(Counter)

    for event in events:
        alias = str(event["alias"])
        alias_counts[alias] += 1
        by_source[str(event["source_id"])][alias] += 1
        by_dataset_type[str(event["dataset_type"])][alias] += 1
        alias_examples.setdefault(
            alias,
            {
                "source_id": str(event["source_id"]),
                "dataset_id": str(event["dataset_id"]),
                "dataset_type": str(event["dataset_type"]),
            },
        )

    top_aliases = []
    for alias, count in alias_counts.most_common(top_n):
        top_aliases.append(
            {
                "alias": alias,
                "count": count,
                **alias_examples[alias],
            }
        )

    return {
        "total_unknown_alias_events": sum(alias_counts.values()),
        "unique_unknown_aliases": len(alias_counts),
        "top_unknown_aliases": top_aliases,
        "by_source": {
            source_id: [
                {"alias": alias, "count": count}
                for alias, count in counter.most_common(top_n)
            ]
            for source_id, counter in sorted(by_source.items())
        },
        "by_dataset_type": {
            dataset_type: [
                {"alias": alias, "count": count}
                for alias, count in counter.most_common(top_n)
            ]
            for dataset_type, counter in sorted(by_dataset_type.items())
        },
    }


def build_mapping_debug_summary(records: list[dict[str, Any]], top_n: int = 50) -> dict[str, Any]:
    by_method = Counter()
    by_domain = Counter()
    unmapped_aliases = Counter()
    blocked_aliases = Counter()
    llm_aliases = Counter()

    for record in records:
        method = str(record["mapping_method"])
        domain = str(record["mapping_domain"])
        original = str(record["original_column"])

        by_method[method] += 1
        by_domain[domain] += 1

        if method == "unmapped":
            unmapped_aliases[original] += 1
        elif method == "blocked":
            blocked_aliases[original] += 1
        elif method == "llm":
            llm_aliases[original] += 1

    return {
        "counts_by_method": dict(sorted(by_method.items())),
        "counts_by_domain": dict(sorted(by_domain.items())),
        "top_unmapped_aliases": [
            {"alias": alias, "count": count}
            for alias, count in unmapped_aliases.most_common(top_n)
        ],
        "top_blocked_aliases": [
            {"alias": alias, "count": count}
            for alias, count in blocked_aliases.most_common(top_n)
        ],
        "top_llm_aliases": [
            {"alias": alias, "count": count}
            for alias, count in llm_aliases.most_common(top_n)
        ],
    }
