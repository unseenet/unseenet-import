"""Facebook's *Download your information*, in JSON (#1).

Only the person's own posts (the ``your_posts`` files) with their text, date, own
pictures and links, and the profile's name, intro and picture. Never comments,
messages, friends, reactions, tags or other people's posts - those files are not read
at all (UN-RFC 0049 section 6.2).

Facebook writes text as UTF-8 bytes each escaped as a Latin-1 character ("Ã¦" for
"æ"); ``fix`` turns it back. Both the layout since 2024 (``your_facebook_activity/``)
and the older one are read."""

from __future__ import annotations

import json
from pathlib import PurePosixPath

from ..model import Picture, Post, Profile, Source
from . import from_epoch, links_in

NETWORK = "facebook"
POSTS = r"(^|/)(your_facebook_activity/)?posts/your_posts[^/]*\.json$"
PROFILE = r"(^|/)(personal_information/)?profile_information/profile_information\.json$"
PHOTOS = r"(^|/)profile_information/profile_photos\.json$"
SKIPPED = ("comments", "messages", "friends", "reactions", "groups")


def recognise(names) -> bool:
    import re
    return any(re.search(POSTS, n) for n in names) or any(re.search(PROFILE, n) for n in names)


def fix(text) -> str:
    """Facebook's mojibake undone: each character was one byte of UTF-8."""
    if not isinstance(text, str):
        return ""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def _json(export, name):
    return json.loads(export.read(name).decode("utf-8"))


def _picture(export, uri, alt="") -> Picture | None:
    uri = str(uri or "").lstrip("/")
    for name in (uri, *(n for n in export.names() if n.endswith("/" + uri))):
        if export.has(name):
            return Picture(PurePosixPath(name).name, export.read(name), fix(alt))
    return None


def read(export) -> Source:
    profile = Profile(NETWORK)
    notes: list[str] = []
    found = export.find(PROFILE)
    if found:
        p = _json(export, found[0]).get("profile_v2") or {}
        profile.name = fix((p.get("name") or {}).get("full_name", ""))
        profile.about = fix((p.get("intro_bio") or {}).get("value", "") if isinstance(p.get("intro_bio"), dict)
                            else p.get("intro_bio", ""))
        profile.links = [fix(w.get("address", w) if isinstance(w, dict) else w)
                         for w in p.get("websites", []) if w]
    photos = export.find(PHOTOS)
    if photos:
        data = _json(export, photos[0])
        items = data.get("profile_photos_v2") or data.get("photos") or []
        if items:
            profile.picture = _picture(export, items[0].get("uri"))
    posts: list[Post] = []
    for name in export.find(POSTS):
        data = _json(export, name)
        items = data if isinstance(data, list) else data.get("status_updates_v2", [])
        for item in items:
            text = "\n\n".join(fix(d["post"]) for d in item.get("data", []) if d.get("post"))
            pictures, links = [], []
            for att in item.get("attachments", []):
                for d in att.get("data", []):
                    media = d.get("media")
                    if media and media.get("uri"):
                        pic = _picture(export, media["uri"], media.get("description", ""))
                        if pic is not None and pic.name.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                            pictures.append(pic)
                        elif pic is not None:
                            notes.append(f"{name}: a video or other file left out ({pic.name})")
                        if not text and media.get("description"):
                            text = fix(media["description"])
                    ext = d.get("external_context") or {}
                    if ext.get("url"):
                        links.append(fix(ext["url"]))
            if not text and not pictures and not links:
                continue
            links = list(dict.fromkeys(links + links_in(text)))
            if links and not any(u in text for u in links):
                text = (text + "\n\n" if text else "") + "\n".join(links)
            posts.append(Post(NETWORK, from_epoch(item.get("timestamp")), text, pictures=pictures,
                              links=links, origin_from=profile.name, source=name))
    posts.sort(key=lambda p: p.origin_date.timestamp() if p.origin_date else 0, reverse=True)
    left = sorted({s.split("/")[-1] for n in export.names() for s in SKIPPED
                   if f"/{s.split('/')[-1]}" in f"/{n}"})
    if left:
        notes.append("Not read, as Unseenet only brings your own posts and profile: "
                     + ", ".join(left))
    return Source(NETWORK, profile, posts, notes)
