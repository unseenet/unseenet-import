"""The adapters and the merge, on small made-up exports (no real data)."""
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from unseenet_import import adapters
from unseenet_import.adapters import facebook
from unseenet_import.merge import merge
from unseenet_import.model import Post

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def _zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data if isinstance(data, bytes) else json.dumps(data))
    return path


def _moji(s):                                      # as Facebook writes it
    return s.encode("utf-8").decode("latin-1")


@pytest.fixture
def fb(tmp_path):
    return _zip(tmp_path / "facebook.zip", {
        "personal_information/profile_information/profile_information.json":
            {"profile_v2": {"name": {"full_name": _moji("Søren Æblegård")},
                            "websites": [{"address": "https://example.org"}]}},
        "your_facebook_activity/posts/your_posts__check_ins__photos_and_videos_1.json": [
            {"timestamp": 1690000000, "data": [{"post": _moji("Så er vi på Askø")}],
             "attachments": [{"data": [{"media": {"uri": "your_facebook_activity/posts/media/a/1.jpg",
                                                  "description": "Havet"}}]}]},
            {"timestamp": 1700000000, "data": [{"post": "Read this"}],
             "attachments": [{"data": [{"external_context": {"url": "https://example.com/x"}}]}]},
            {"timestamp": 1710000000, "attachments": [{"data": [{"media": {"uri": "your_facebook_activity/posts/media/a/2.mp4"}}]}]},
        ],
        "your_facebook_activity/posts/media/a/1.jpg": JPEG,
        "your_facebook_activity/posts/media/a/2.mp4": b"video",
        "your_facebook_activity/messages/inbox/x/message_1.json": {"messages": [{"content": "hemmelig"}]},
        "your_facebook_activity/comments_and_reactions/comments.json": {"comments": []},
    })


def test_facebook(fb):
    s = adapters.open_source(fb)
    assert s.network == "facebook" and s.profile.name == "Søren Æblegård"
    assert s.profile.links == ["https://example.org"]
    texts = [p.text for p in s.posts]
    assert texts[0] == "Read this\n\nhttps://example.com/x"                 # newest first, link kept
    askoe = next(p for p in s.posts if "Askø" in p.text)
    assert askoe.text == "Så er vi på Askø" and askoe.pictures[0].alt == "Havet"
    assert askoe.origin_date == datetime.fromtimestamp(1690000000, timezone.utc)
    assert len(s.posts) == 2                                              # the video-only one dropped
    assert all("hemmelig" not in p.text for p in s.posts)
    assert any("video" in n for n in s.notes) and any("messages" in n for n in s.notes)


def test_mastodon(tmp_path):
    me = "https://social.example/users/sonia"
    pub = ["https://www.w3.org/ns/activitystreams#Public"]
    path = _zip(tmp_path / "mastodon.zip", {
        "actor.json": {"id": me, "name": "Sonia", "preferredUsername": "sonia",
                       "summary": "<p>Tegner &amp; maler</p>", "icon": {"url": "/avatar.png"},
                       "attachment": [{"type": "PropertyValue", "name": "Site",
                                       "value": '<a href="https://sonia.example">sonia.example</a>'}]},
        "avatar.png": JPEG,
        "outbox.json": {"orderedItems": [
            {"type": "Create", "object": {"type": "Note", "to": pub, "published": "2025-05-01T10:00:00Z",
                                          "url": me + "/1", "content": '<p>Ny tegning <a href="https://social.example/tags/art" class="hashtag">#<span>art</span></a></p><p>Se <a href="https://x.example/a"><span>x.example/a</span></a></p>',
                                          "attachment": [{"mediaType": "image/png", "url": "/media_attachments/files/1.png", "name": "En kat"}]}},
            {"type": "Announce", "object": "https://other.example/1"},
            {"type": "Create", "object": {"type": "Note", "to": [me + "/followers"], "content": "<p>kun venner</p>"}},
            {"type": "Create", "object": {"type": "Note", "to": pub, "inReplyTo": "https://other.example/2", "content": "<p>svar</p>"}},
        ]},
        "media_attachments/files/1.png": JPEG,
    })
    s = adapters.open_source(path)
    assert s.network == "mastodon" and s.profile.name == "Sonia" and s.profile.about == "Tegner & maler"
    assert s.profile.links == ["https://sonia.example"] and s.profile.picture is not None
    (p,) = s.posts
    assert p.text == "Ny tegning #art\n\nSe https://x.example/a" and p.pictures[0].alt == "En kat"
    assert "1 boosts" in s.notes[0] and "1 private" in s.notes[0] and "1 replies" in s.notes[0]


def _article(ident, body, subject="Hej", when=None):
    from unseenet.core.article import new_article
    return new_article("feed@x", subject, body, now=when).finalize(ident, 0)


def test_an_unseenet_export(tmp_path):
    from unseenet.core import crypto
    me, other = crypto.Identity.generate(), crypto.Identity.generate()
    mine = _article(me, "Fra den gamle nøgle\n").to_bytes()
    forged = bytearray(_article(me, "Ændret bagefter\n").to_bytes())
    forged[forged.index(b"bagefter")] ^= 1                                  # no longer as signed
    theirs = _article(other, "Ikke min\n").to_bytes()
    path = _zip(tmp_path / "unseenet-export.zip", {
        "export.json": {"version": 1, "key": me.key_text, "fingerprint": me.fingerprint, "private": False},
        "profile.json": {"name": "Andreas", "profile": {"about": "Om mig"}},
        "articles/a.eml": mine, "articles/b.eml": bytes(forged), "articles/c.eml": theirs,
    })
    s = adapters.open_source(path)
    (p,) = s.posts
    assert p.text == "Fra den gamle nøgle" and p.title == "Hej" and p.proof == mine and p.origin_id
    assert "2 not signed by this key" in s.notes[0]
    assert s.profile.name == "Andreas" and s.profile.about == "Om mig"


def test_a_sealed_unseenet_export_needs_its_passphrase(tmp_path):
    from unseenet.core import crypto
    from unseenet.core.vault import seal
    me = crypto.Identity.generate()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("export.json", json.dumps({"version": 1, "key": me.key_text, "private": True}))
        z.writestr("articles/a.eml", _article(me, "Hej\n").to_bytes())
    sealed = tmp_path / "e.zip.sealed"
    sealed.write_bytes(seal(buf.getvalue(), "sætning", ops=1, mem=8192 * 1024))
    with pytest.raises(ValueError, match="passphrase"):
        adapters.open_source(sealed)
    assert len(adapters.open_source(sealed, "sætning").posts) == 1


def test_not_an_export(tmp_path):
    with pytest.raises(ValueError, match="not an export"):
        adapters.open_source(_zip(tmp_path / "x.zip", {"hello.txt": b"hi"}))


def test_merge():
    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    from unseenet_import.model import Picture, Profile, Source
    a = Source("facebook", Profile("facebook", name="Søren", links=["https://a.example"]),
               [Post("facebook", t0, "Godt nytår! https://fb.example/1", pictures=[Picture("1.jpg", b"1")]),
                Post("facebook", t0 - timedelta(days=30), "Gammel tekst")])
    b = Source("mastodon", Profile("mastodon", name="soren", about="Bio", links=["https://a.example", "https://b.example"]),
               [Post("mastodon", t0 + timedelta(hours=2), "Godt nytår!", pictures=[Picture("2.jpg", b"2")]),
                Post("mastodon", t0 + timedelta(days=2), "Ny")])
    m = merge([a, b], have=[("gammel tekst", t0 - timedelta(days=30))])
    assert [n for n, _ in m.choices["name"]] == ["facebook", "mastodon"] and m.choices["about"] == [("mastodon", "Bio")]
    assert m.links == ["https://a.example", "https://b.example"]
    assert [p.text for p in m.posts] == ["Ny", "Godt nytår! https://fb.example/1"]   # newest first
    assert m.duplicates == 1 and m.already == 1
    assert {x.name for x in m.posts[1].pictures} == {"1.jpg", "2.jpg"}
    assert facebook.fix("plain") == "plain"
