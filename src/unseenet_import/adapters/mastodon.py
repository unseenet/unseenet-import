"""Mastodon's export: ``outbox.json``, ``actor.json`` and ``media_attachments/`` (#2).

Only the person's own public and unlisted posts with their pictures - not boosts of
other people's posts (``Announce``), not direct messages or followers-only posts (they
were not meant for everyone), not replies to other people (half a conversation). The
profile's name, bio, fields as links, and avatar."""

from __future__ import annotations

import json

from ..model import Picture, Post, Profile, Source
from . import from_iso, html_text, links_in

NETWORK = "mastodon"
PUBLIC = "https://www.w3.org/ns/activitystreams#Public"


def recognise(names) -> bool:
    return any(n.split("/")[-1] == "outbox.json" for n in names) and \
        any(n.split("/")[-1] == "actor.json" for n in names)


def _file(export, url) -> bytes | None:
    path = str(url or "").split("?", 1)[0].lstrip("/")
    for name in export.names():
        if path and (name == path or name.endswith("/" + path)):
            return export.read(name)
    return None


def read(export) -> Source:
    base = next(n for n in export.names() if n.split("/")[-1] == "actor.json")
    actor = json.loads(export.read(base))
    root = base[: -len("actor.json")]
    profile = Profile(NETWORK, name=actor.get("name") or actor.get("preferredUsername", ""),
                      about=html_text(actor.get("summary", "")))
    for f in actor.get("attachment", []):
        if f.get("type") == "PropertyValue":
            profile.links += links_in(html_text(f.get("value", "")))
    icon = actor.get("icon") or {}
    if icon.get("url"):
        data = _file(export, icon["url"])
        if data:
            profile.picture = Picture(icon["url"].split("/")[-1], data)
    me = actor.get("id", "")
    outbox = json.loads(export.read(root + "outbox.json"))
    posts, notes = [], []
    skipped = {"boosts": 0, "private": 0, "replies": 0}
    for act in outbox.get("orderedItems", []):
        if act.get("type") == "Announce":
            skipped["boosts"] += 1
            continue
        obj = act.get("object")
        if act.get("type") != "Create" or not isinstance(obj, dict) or obj.get("type") != "Note":
            continue
        audience = set(obj.get("to", [])) | set(obj.get("cc", []))
        if PUBLIC not in audience:
            skipped["private"] += 1
            continue
        reply = obj.get("inReplyTo")
        if reply and me and not str(reply).startswith(me):
            skipped["replies"] += 1
            continue
        pictures = []
        for att in obj.get("attachment", []):
            if str(att.get("mediaType", "")).startswith("image/"):
                data = _file(export, att.get("url"))
                if data:
                    pictures.append(Picture(att["url"].split("/")[-1], data, att.get("name") or ""))
        text = html_text(obj.get("content", ""))
        if obj.get("summary"):                               # a content warning
            text = f"**{obj['summary']}**\n\n{text}"
        posts.append(Post(NETWORK, from_iso(obj.get("published")), text, pictures=pictures,
                          links=links_in(text), origin_id=obj.get("url") or obj.get("id", ""),
                          origin_from=actor.get("preferredUsername", ""), source="outbox.json"))
    posts.sort(key=lambda p: p.origin_date.timestamp() if p.origin_date else 0, reverse=True)
    if any(skipped.values()):
        notes.append("Left out: " + ", ".join(f"{n} {k}" for k, n in skipped.items() if n)
                     + " (other people's posts you boosted, posts not meant for everyone, "
                       "and replies to others)")
    return Source(NETWORK, profile, posts, notes)
