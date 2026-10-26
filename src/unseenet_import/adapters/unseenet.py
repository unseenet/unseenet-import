"""An Unseenet export (UN-RFC 0049 section 7.3, #10): the person's profile and their
own posts, to bring to a new key.

Every article is checked first: its signature must hold and its key must be the
export's - an export can be edited by anyone who had it, the signatures cannot.
Encrypted articles (closed groups) cannot be read here and are left out, as are
reactions, pages and control articles. Each post keeps the old article as signed in
``proof``; posting it as ``Origin-Proof`` (and the old Message-ID as ``Origin-ID``)
links the new key to the old for good, so that is the person's choice, off by default."""

from __future__ import annotations

import json
from email.utils import parsedate_to_datetime

from ..model import Picture, Post, Profile, Source
from . import links_in

NETWORK = "unseenet"


def recognise(names) -> bool:
    return "export.json" in names and any(n.startswith("articles/") for n in names)


def read(export) -> Source:
    from unseenet.core import blobs as bl
    from unseenet.core import crypto
    from unseenet.core.article import Article, ArticleError
    info = json.loads(export.read("export.json"))
    key = crypto.key_from_text(info["key"])
    prof = json.loads(export.read("profile.json")) if export.has("profile.json") else {}
    p = prof.get("profile") or {}
    profile = Profile(NETWORK, name=p.get("name") or prof.get("name", ""),
                      about=p.get("about", "") or p.get("text", ""),
                      links=[str(x) for x in p.get("links", []) if x])
    pic = next((n for n in export.names() if n.startswith("profile/picture.")), None)
    if pic:
        profile.picture = Picture(pic.split("/")[-1], export.read(pic))
    posts, notes = [], []
    left = {"not signed by this key": 0, "encrypted": 0, "reactions, pages and others": 0}
    for name in export.find(r"^articles/"):
        raw = export.read(name)
        try:
            art = Article.from_bytes(raw)
            art.verify_signature()
        except (ArticleError, ValueError):
            left["not signed by this key"] += 1
            continue
        if art.author_key != key:
            left["not signed by this key"] += 1
            continue
        if art.get("Encrypted"):
            left["encrypted"] += 1
            continue
        kind = (art.get("Message-Kind") or "post").strip().lower()
        if kind not in ("post", "chat") or art.get("Page") or art.get("Control") or art.get("Supersedes") is not None and not art.body.strip():
            left["reactions, pages and others"] += 1
            continue
        pictures = []
        try:
            for a in bl.parse_attachments([(k, v) for k, v in art.headers if k.startswith("Attachment-")]):
                path = "files/" + a["blob"].replace(":", "_")
                if export.has(path) and a.get("type", "").startswith("image/"):
                    pictures.append(Picture(a.get("name") or a["blob"][-12:], export.read(path), a.get("alt", "")))
        except Exception:
            pass
        try:
            when = parsedate_to_datetime(art["Date"])
        except (KeyError, TypeError, ValueError):
            when = None
        text = art.body.rstrip("\n")
        posts.append(Post(NETWORK, when, text, title=(art.get("Subject") or "") if kind == "post" else "",
                          pictures=pictures, links=links_in(text), origin_id=art.message_id,
                          origin_from=info["key"], proof=raw, source=name))
    posts.sort(key=lambda p: p.origin_date.timestamp() if p.origin_date else 0, reverse=True)
    if any(left.values()):
        notes.append("Left out: " + ", ".join(f"{n} {k}" for k, n in left.items() if n))
    if info.get("private"):
        notes.append("Private messages in the export are not imported: they were between you "
                     "and others.")
    return Source(NETWORK, profile, posts, notes)
