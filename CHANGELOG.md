# Changelog

## [Unreleased]

- **The engine** (#1, #2, #4, #10): a model of what is imported (profile, posts with
  their first-published date, pictures, links - nothing else) and adapters that read
  an export where it lies, never uploading it: **Facebook** (*Download your
  information*, JSON, both layouts, its broken æøå mended), **Mastodon** (outbox and
  actor; no boosts, no posts not meant for everyone, no replies to others) and
  **Unseenet** (an export of another key, every article's signature checked first).
  Several sources merge into one profile (chosen field by field) and one feed, the
  same post shared twice kept once, what is already in Unseenet left out.
