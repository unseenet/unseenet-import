<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-dark.svg">
    <img src="https://raw.githubusercontent.com/unseenet/unseenet/main/assets/logo-light.svg" alt="Unseenet" width="360">
  </picture>
</p>

<h1 align="center">unseenet-import</h1>

<p align="center"><b>Start here.</b><br>
Bring your profile, posts and pictures from Facebook, X, Mastodon and other networks into <a href="https://unseenet.org">Unseenet</a> - merged into one profile, feed and site, on your own machine.</p>

> **Being built.** The engine is here: adapters for Facebook, Mastodon and
> Unseenet exports, and merging them into one profile and feed. The draft,
> posting, preview and start page come next (see the issues). The protocol
> side is UN-RFC 0049.

Coming to a new network usually means starting with an empty page. With
unseenet-import you start with what you already have: download your data
from the networks you use, open it here, and see how it will look as your
Unseenet profile, feed and site before anything is posted. Mix several
sources, edit until you are happy, then post - into a new vault or one you
already have.

It will live at **starthere.unseenet.net**, running in your browser, and as
a program you can run yourself, like the graphical client.

## How it will work

1. **Get your data.** The page explains, network by network, how to
   download your own export (Facebook's *Download your information* as
   JSON, X's archive, Mastodon's export, Instagram, Bluesky …).
2. **Open it here.** The export is read **on your machine**, in the browser
   or the program. It is never uploaded to any server.
3. **Merge.** Several sources become one profile: you choose name, text and
   picture field by field, links are gathered, and a post you shared on two
   networks is imported once. Anything already on your Unseenet profile
   counts too, so you can come back later and only the new is added.
4. **Preview and edit.** See your profile, your feed and your site exactly
   as the Unseenet clients show them. Leave posts out, change text, choose
   pictures.
5. **Post.** Your posts go out with the date they were first published
   shown ("Imported from Facebook · originally 3 August"). A new key has to
   ripen and nodes limit pictures per day, so the rest is posted over the
   coming days, newest first, while the draft waits on your machine.

## What stays on your machine

- **Your exports and your draft.** Kept encrypted with a key from your
  vault, but *not* in the vault - the vault goes to your phone, a draft of
  hundreds of pictures should not. When everything is posted, you are
  offered to delete them.
- **Nothing is sent anywhere** except the posts you choose, posted like
  any client posts, over Tor or through a web entrance.

## What is imported - and what never is

- **Yours:** your posts, the pictures you published, your profile.
- **Never other people's:** comments, posts on your wall by others,
  messages, friend lists, tags, other people's pictures. Once in Unseenet,
  nobody can remove them again, and they are not yours to post.
- **Picture metadata** (location, camera, times) is removed by default.

**Think before you import.** Your name, picture and posts tie your Unseenet
key to who you are elsewhere, for good. That is fine for most people. If you
need to stay hidden, do not import - start a fresh identity instead.

## Built on the core

Everything that touches the network - vaults, keys, ripening, postage,
pictures, posting - is the [unseenet](https://github.com/unseenet/unseenet)
core, the same code every client uses. In the browser it runs as in the
[web entrance](https://github.com/unseenet/unseenet-entrance): the core in
Pyodide. The look is the [graphical client](https://github.com/unseenet/unseenet-gui)'s,
so the preview is what people will see. What lives here is the import: one
adapter per network, merging, the draft and the editor.

This is its own program, not part of the graphical client, so the client
stays small for daily use.

## License

Code Apache-2.0. Logo CC BY 4.0, from the Unseenet project.
