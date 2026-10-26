"""The draft: what will be imported, as the person edits it (#5, UN-RFC 0049 section 6.1).

It stays on the machine where the import is made until everything is posted, encrypted
with a key derived from the identity in the vault (``key_for``) - but not in the vault,
which travels to phones. One file (``save``/``load``), so it can also be saved and opened
again where browser storage may be cleared. The posting queue's own state lives in it
too, so nothing about the posts is ever on disk in the clear.

    Draft.from_merged(merged) -> Draft          # every post included, nothing linked
    draft.save(path, key); Draft.load(path, key)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .model import Picture, Post

VERSION = 1
HEAD = b"UNSEENET-IMPORT-DRAFT-1\n"


def key_for(session) -> bytes:
    """The draft's key: from the identity's secret key, for this purpose only."""
    seed = session.identity().seed
    return hashlib.blake2b(b"unseenet-import draft v1", key=seed, digest_size=32).digest()


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


@dataclass
class DraftPost:
    id: str                               # stable within the draft: the queue's key
    network: str
    origin_date: str | None               # RFC 3339 UTC
    text: str
    title: str = ""
    pictures: list[dict] = field(default_factory=list)   # {"name", "data" (base64), "alt"}
    links: list[str] = field(default_factory=list)
    origin_id: str = ""
    origin_from: str = ""
    proof: str = ""                       # base64 of the old article (Unseenet only)
    include: bool = True

    @classmethod
    def from_post(cls, p: Post, n: int) -> "DraftPost":
        when = p.origin_date.strftime("%Y-%m-%dT%H:%M:%SZ") if p.origin_date else None
        ident = hashlib.sha256(f"{p.network}|{when}|{p.text}".encode()).hexdigest()[:16]
        return cls(f"{n:05d}-{ident}", p.network, when, p.text, p.title,
                   [{"name": x.name, "data": _b64(x.octets), "alt": x.alt} for x in p.pictures],
                   list(p.links), p.origin_id, p.origin_from, _b64(p.proof) if p.proof else "")

    def picture_files(self) -> list[Picture]:
        return [Picture(x["name"], base64.b64decode(x["data"]), x.get("alt", "")) for x in self.pictures]


@dataclass
class Draft:
    profile: dict = field(default_factory=dict)     # {"name", "about", "links", "picture"}
    choices: dict = field(default_factory=dict)     # field -> [[network, value]] (pictures base64)
    posts: list[DraftPost] = field(default_factory=list)   # newest first
    keep_origin_ids: bool = False         # post Origin-ID (section 4.3): off by default
    link_keys: bool = False               # Unseenet: post Origin-Proof, linking the keys for good
    queue: dict = field(default_factory=dict)       # the posting queue's state
    sources: list[str] = field(default_factory=list)
    made: str = ""

    @classmethod
    def from_merged(cls, merged, sources=()) -> "Draft":
        def value(v):
            return {"name": v.name, "data": _b64(v.octets), "alt": v.alt} if isinstance(v, Picture) else v
        choices = {k: [[n, value(v)] for n, v in opts] for k, opts in merged.choices.items()}
        first = {k: opts[0][1] for k, opts in choices.items()}
        return cls(profile={"name": first.get("name", ""), "about": first.get("about", ""),
                            "links": list(merged.links), "picture": first.get("picture")},
                   choices=choices,
                   posts=[DraftPost.from_post(p, i) for i, p in enumerate(merged.posts)],
                   sources=[str(s) for s in sources],
                   made=datetime.now().astimezone().isoformat(timespec="seconds"))

    def included(self) -> list[DraftPost]:
        return [p for p in self.posts if p.include]

    # --- on disk, encrypted ---
    def to_bytes(self) -> bytes:
        return json.dumps({"v": VERSION, **asdict(self)}, ensure_ascii=False).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "Draft":
        d = json.loads(data)
        if d.pop("v", None) != VERSION:
            raise ValueError("a draft of another version")
        d["posts"] = [DraftPost(**p) for p in d.get("posts", [])]
        return cls(**d)

    def save(self, path, key: bytes) -> Path:
        import nacl.secret
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        box = nacl.secret.SecretBox(key).encrypt(self.to_bytes())
        tmp = path.with_name(path.name + ".new")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(HEAD + box)
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, path, key: bytes) -> "Draft":
        import nacl.exceptions
        import nacl.secret
        data = Path(path).read_bytes()
        if not data.startswith(HEAD):
            raise ValueError("not an import draft")
        try:
            return cls.from_bytes(nacl.secret.SecretBox(key).decrypt(data[len(HEAD):]))
        except nacl.exceptions.CryptoError as exc:
            raise ValueError("this draft was made with another identity") from exc
