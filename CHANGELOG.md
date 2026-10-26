# Changelog

## [Unreleased]

- **The draft and posting** (#5, #7): the draft - profile choices, every post with
  include/leave out, the posting queue's state - is one file encrypted with a key
  from the identity, not in the vault, 0600; another identity cannot open it.
  Posting goes through the core's posting queue into your own feed (started if
  need be), newest first, the profile first; each post with `Origin-Network` and
  `Origin-Date`, `Origin-ID` only if chosen; no mention notices; carried on next
  time. The warning before the first post (UN-RFC 0049 section 10) is here for the
  clients. Linking an old Unseenet key (`Origin-Proof`) waits for the core.

- **The engine** (#1, #2, #4, #10): a model of what is imported (profile, posts with
  their first-published date, pictures, links - nothing else) and adapters that read
  an export where it lies, never uploading it: **Facebook** (*Download your
  information*, JSON, both layouts, its broken æøå mended), **Mastodon** (outbox and
  actor; no boosts, no posts not meant for everyone, no replies to others) and
  **Unseenet** (an export of another key, every article's signature checked first).
  Several sources merge into one profile (chosen field by field) and one feed, the
  same post shared twice kept once, what is already in Unseenet left out.
