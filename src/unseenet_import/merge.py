"""Several sources into one profile and one feed (#4, UN-RFC 0049 section 6.3).

    merge(sources, have=()) -> Merged

The profile is chosen field by field by the person: ``Merged.choices`` has, per field,
what each source offers; ``links`` gathers them all. The same post shared on two
networks is kept once - the same text (letters and digits, links aside) first published
within 36 hours - keeping the earlier, with the pictures of both. What the person
already has in Unseenet (``have``: texts and dates of their own posts) counts, so running
again only adds what is new. Nothing here asks a server."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import timedelta

from .model import Post, Source

SAME_WITHIN = timedelta(hours=36)


def fingerprint(text: str) -> str:
    """A post's text for comparing: links, punctuation and case left out."""
    t = re.sub(r"https?://\S+", " ", text or "")
    t = unicodedata.normalize("NFKC", t).casefold()
    return " ".join(re.findall(r"\w+", t))


@dataclass
class Merged:
    choices: dict[str, list[tuple[str, object]]] = field(default_factory=dict)  # field -> [(network, value)]
    links: list[str] = field(default_factory=list)
    posts: list[Post] = field(default_factory=list)            # newest first
    duplicates: int = 0
    already: int = 0


def _same(a: Post, b_text: str, b_date) -> bool:
    if fingerprint(a.text) != b_text or not b_text:
        return False
    if a.origin_date is None or b_date is None:
        return True
    return abs(a.origin_date - b_date) <= SAME_WITHIN


def merge(sources: list[Source], have=()) -> Merged:
    out = Merged()
    for s in sources:
        for name, value in (("name", s.profile.name), ("about", s.profile.about),
                            ("picture", s.profile.picture)):
            if value:
                out.choices.setdefault(name, []).append((s.network, value))
        out.links += s.profile.links
    out.links = list(dict.fromkeys(out.links))
    seen = [(fingerprint(t), d) for t, d in have]
    kept: list[tuple[str, Post]] = []
    every = sorted((p for s in sources for p in s.posts),
                   key=lambda p: p.origin_date.timestamp() if p.origin_date else 0)
    for p in every:                                       # oldest first: the first one stays
        fp = fingerprint(p.text)
        if any(_same(p, t, d) for t, d in seen):
            out.already += 1
            continue
        twin = next((k for f, k in kept if fp and f == fp and _same(p, f, k.origin_date)), None)
        if twin is not None:
            names = {x.name for x in twin.pictures}
            twin.pictures += [x for x in p.pictures if x.name not in names]
            twin.links = list(dict.fromkeys(twin.links + p.links))
            out.duplicates += 1
            continue
        kept.append((fp, p))
    out.posts = [p for _, p in reversed(kept)]
    return out
