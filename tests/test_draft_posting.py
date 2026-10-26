"""#5 the draft, encrypted and not in the vault; #7 posting it through the core."""
import json
from datetime import datetime, timezone

import pytest

import unseenet.client.session as sess
from unseenet.client.session import Session
from unseenet.core.article import Article
from unseenet.core.blobs import BlobStore
from unseenet.core.store import Store
from unseenet.core.vault import Vault
from unseenet.node.server import Node, NodeConfig
from unseenet_import import draft as dr
from unseenet_import import posting
from unseenet_import.merge import merge
from unseenet_import.model import Picture, Post, Profile, Source

KDF = {"ops": 1, "mem": 8192 * 1024}


def _jpeg():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (10, 120, 200)).save(buf, "JPEG")
    return buf.getvalue()


def _source():
    t = lambda d: datetime(2024, 5, d, 12, tzinfo=timezone.utc)   # noqa: E731
    return Source("facebook", Profile("facebook", name="Søren", about="Om mig",
                                      links=["https://example.org"]),
                  [Post("facebook", t(3), "Den nyeste", pictures=[Picture("a.jpg", _jpeg(), "Havet")]),
                   Post("facebook", t(2), "Den midterste"),
                   Post("facebook", t(1), "Den ældste", origin_id="fb-1")])


@pytest.fixture
async def me(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSEENET_INSECURE_FAST_KDF", "1")
    monkeypatch.setattr(sess, "DEFAULT_POW", 8)
    node = Node(Store(), NodeConfig(min_pow=8, forward_delay=(0, 0), sites="accept"))
    node.config.blobs = {"max_size": 1048576}
    node.blobs = BlobStore()
    server = await node.serve("127.0.0.1", 0)
    s = Session(Vault.open(tmp_path / "me.vault", "pw", **KDF), status=lambda *_: None)
    s.new_identity("me", "Me")
    s.add_node("127.0.0.1:%d" % server.sockets[0].getsockname()[1])
    yield s, node
    await s.close()
    server.close()


async def test_the_draft_is_encrypted_and_for_this_identity(me, tmp_path):
    s, _ = me
    d = dr.Draft.from_merged(merge([_source()]))
    assert [p.text for p in d.posts] == ["Den nyeste", "Den midterste", "Den ældste"]
    assert d.profile["about"] == "Om mig" and not d.keep_origin_ids and not d.link_keys
    path = d.save(tmp_path / "draft.bin", dr.key_for(s))
    raw = path.read_bytes()
    assert b"nyeste" not in raw and "Søren".encode() not in raw
    import os
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
    back = dr.Draft.load(path, dr.key_for(s))
    assert back.posts[0].picture_files()[0].alt == "Havet"
    with pytest.raises(ValueError, match="another identity"):
        dr.Draft.load(path, b"\x01" * 32)


async def test_posting_a_draft(me, tmp_path):
    s, node = me
    await s.ensure_inbox()
    d = dr.Draft.from_merged(merge([_source()]))
    d.posts[1].include = False                              # left out by the person
    saved = []

    def save(draft):
        saved.append(draft.to_bytes())
    left = await posting.post_draft(s, d, save)
    assert left["left"] == 0 and len(d.queue["done"]) == 2 and d.queue["profile_done"]
    feed = s.personal_group("feed")
    arts = [Article.from_bytes(node.store.get(x["message_id"])) for x in d.queue["done"]]
    assert [a["Origin-Network"] for a in arts] == ["facebook", "facebook"]
    assert arts[0].body.startswith("Den nyeste") and arts[0].get("Blobs")      # its picture
    assert arts[1].get("Origin-ID") is None                                   # not kept by default
    assert arts[1]["Origin-Date"].startswith("2024-05-01")
    assert all(a["Newsgroups"] == feed for a in arts)
    assert (s.my_profile() or {}).get("about") == "Om mig"
    assert saved and json.loads(saved[-1])["queue"]["done"]
    again = await posting.post_draft(s, d, save)                            # nothing new
    assert again["left"] == 0 and len(d.queue["done"]) == 2


def test_linking_keys_is_refused_for_now(tmp_path):
    d = dr.Draft.from_merged(merge([_source()]))
    d.link_keys = True
    with pytest.raises(posting.PostingError, match="not possible yet"):
        posting.queue_items(d, "feed@x", tmp_path)
