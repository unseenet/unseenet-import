"""Posting a draft through the core, like any client (#7, UN-RFC 0049 section 6.4).

Into the person's own feed, newest first, through the core's posting queue (paced by
postage, ripening and file quotas; carried on next time). ``Date`` is the time of
posting (section 3.1); each post carries its origin (section 4): network and date
always, ``Origin-ID`` only if the person chose to keep ids. No mention notices (6.2).
The profile first, from what the person chose.

``Origin-Proof`` (an Unseenet export, linking the keys, section 7.3) needs the core to
write it; until then ``link_keys`` is refused with a sentence, and the default - not
linking - is what is posted.

Before the first post a client shows ``WARNING`` (section 10) and asks.
"""

from __future__ import annotations

import base64
import shutil
import tempfile
from pathlib import Path

from .draft import Draft

WARNING = ("Importing ties this key to who you are elsewhere, for good: anyone who sees "
           "the same posts there and here can tell it is you. If you need to be someone new "
           "here, don't import.")


class PostingError(ValueError):
    pass


def queue_items(draft: Draft, feed: str, folder: Path) -> list[dict]:
    """The queue's items for what is left to post: pictures written to ``folder`` (the
    queue posts files by path), origins as the person chose."""
    if draft.link_keys:
        raise PostingError("Linking the old key with Origin-Proof is not possible yet: "
                           "import without it (the default).")
    done = {d.get("key") for d in draft.queue.get("done", [])}
    out = []
    for p in draft.included():
        if p.id in done:
            continue
        origin = {"network": p.network, "date": p.origin_date}
        if draft.keep_origin_ids and p.origin_id:
            origin["id"] = p.origin_id
        files = []
        for i, pic in enumerate(p.picture_files()):
            f = folder / p.id / f"{i}-{Path(pic.name).name or 'picture'}"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(pic.octets)
            files.append(str(f))
        out.append({"group": feed, "subject": p.title or subject_of(p.text),
                    "body": p.text if p.text.strip() else " ",
                    "files": files or None, "origin": origin, "key": p.id})
    return out


def subject_of(text: str) -> str:
    first = next((ln.strip(" #*") for ln in text.splitlines() if ln.strip()), "")
    return (first[:60] + "…") if len(first) > 60 else first


async def publish_profile(session, draft: Draft) -> None:
    """The profile as chosen: about and links (and the picture), before the posts."""
    prof = draft.profile
    links = [{"kind": "web", "value": u} for u in prof.get("links", [])
             if str(u).startswith("http")][:16]
    await session.publish_profile({"v": 1, "about": (prof.get("about") or "")[:2000], "links": links})
    pic = prof.get("picture")
    if isinstance(pic, dict) and pic.get("data"):
        await session.publish_picture(session.make_picture(base64.b64decode(pic["data"]),
                                                           pic.get("alt", "")))


async def post_draft(session, draft: Draft, save, *, progress=None, profile: bool = True) -> dict:
    """Post what is left of ``draft`` into the person's feed (started if need be);
    ``save(draft)`` keeps the draft - and so the queue - after every post. Returns the
    queue's ``estimate()``: what is left, and how long it may take."""
    if not session.has_personal_group("feed"):
        await session.start_personal_group("feed")
    feed = session.personal_group("feed")
    folder = Path(tempfile.mkdtemp(prefix="unseenet-import-"))
    folder.chmod(0o700)
    try:
        items = queue_items(draft, feed, folder)          # refuses before anything is sent
        if profile and not draft.queue.get("profile_done"):
            await publish_profile(session, draft)
            draft.queue["profile_done"] = True
            save(draft)

        def load():
            return {"items": items, "done": draft.queue.get("done", []),
                    "failed": draft.queue.get("failed", []),
                    "waiting_until": draft.queue.get("waiting_until", 0)}

        def keep(state):
            draft.queue.update({k: state.get(k) for k in ("done", "failed", "waiting_until")})
            save(draft)
        q = session.posting_queue(load=load, save=keep, progress=progress)
        return await q.run()
    finally:
        shutil.rmtree(folder, ignore_errors=True)
