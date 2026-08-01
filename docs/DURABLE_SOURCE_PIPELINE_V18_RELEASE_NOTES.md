# Authentic AI — Durable Source Pipeline V18

## Purpose

V18 removes artifact generation's dependency on the compact text shown in the chat transcript. A large pasted source is persisted before its visible chat preview is compacted, and the source can be recovered after navigation, refresh, retry, or copying the compact preview into another chat.

## Changes

- Persists every substantial document source in the browser's durable IndexedDB source vault.
- Raises the retained source budget from 2,000,000 to 4,000,000 characters.
- Adds an opaque source reference to compact previews without displaying it in the rendered message.
- Recovers copied compact previews by exact source reference.
- Falls back to deterministic beginning-and-ending matching for older compact previews created before V18.
- Hydrates older compact messages during the next request even when those messages do not contain a source reference.
- Resolves the authoritative source before creation/revision routing, intent detection, continuation detection, and artifact-source selection.
- Reuses the recovered full source rather than submitting the incomplete chat preview.
- Preserves V13 adaptive layouts, V14 explicit-only metadata, V15 creation routing, V16 authoritative-source priority, and V17 instruction boundaries.

## Result

The chat preview is now presentation-only. The full source is the generation authority. Large-source retries no longer require the user to paste the original content again while its durable source record remains available in the browser.
