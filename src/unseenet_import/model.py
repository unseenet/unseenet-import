"""What an adapter reads out of a network's export, and nothing else (UN-RFC 0049
section 6.2): the person's own profile fields and their own posts with text, the date
they were first published, pictures and links. Never comments, other people's posts,
messages, friend lists or tags."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Picture:
    name: str
    octets: bytes
    alt: str = ""


@dataclass
class Post:
    network: str                     # Origin-Network: facebook, mastodon, unseenet, ...
    origin_date: datetime | None     # when it was first published there (UTC)
    text: str                        # Markdown, as UN-RFC 0031 allows
    title: str = ""
    pictures: list[Picture] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    origin_id: str = ""              # the post's id there; posted only if the person chooses
    origin_from: str = ""            # the person's name or handle there
    proof: bytes = b""               # Unseenet only: the old article as signed (section 7.3)
    source: str = ""                 # where in the export it came from, for the report


@dataclass
class Profile:
    network: str
    name: str = ""
    about: str = ""
    links: list[str] = field(default_factory=list)
    picture: Picture | None = None


@dataclass
class Source:
    """One export, read: its profile, its posts (newest first) and notes for the person
    about what was left out and why."""
    network: str
    profile: Profile
    posts: list[Post] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
