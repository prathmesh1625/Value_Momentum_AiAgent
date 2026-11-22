"""Retrieval over the carrier's underwriting guidelines.

Uses BM25 keyword search: no embedding model to download, and it works well on a short,
rule-heavy document. Each numbered rule (e.g. "2.1") is one chunk, so answers can cite it.
"""
from __future__ import annotations

import re
from functools import lru_cache

from rank_bm25 import BM25Okapi

from app import config

RULE_RE = re.compile(r"^(\d+\.\d+)\s+(.*)")


@lru_cache(maxsize=1)
def load_rules() -> list[dict]:
    rules: list[dict] = []
    section = ""
    current: dict | None = None
    for line in config.GUIDELINES_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            current = None
            continue
        m = RULE_RE.match(line.strip())
        if m:
            current = {"id": m.group(1), "section": section, "text": m.group(2)}
            rules.append(current)
        elif current and line.strip():
            current["text"] += " " + line.strip()
    return rules


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


@lru_cache(maxsize=1)
def _index() -> BM25Okapi:
    return BM25Okapi([_tokens(r["section"] + " " + r["text"]) for r in load_rules()])


def search(query: str, k: int = 5) -> list[dict]:
    rules = load_rules()
    scores = _index().get_scores(_tokens(query))
    ranked = sorted(zip(scores, rules), key=lambda x: x[0], reverse=True)
    return [r for s, r in ranked[:k] if s > 0]


def format_rules(rules: list[dict]) -> str:
    return "\n".join(f"[{r['id']}] ({r['section']}) {r['text']}" for r in rules)
