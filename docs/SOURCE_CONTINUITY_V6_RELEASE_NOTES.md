# Authentic AI - Source Continuity V6

## Problem resolved

Large pasted sources are intentionally shown as compact chat previews. Earlier builds could lose access to the hidden full source after conversation persistence or when a later request referred to an older compact preview. The document quality guard then rejected generation even when a completed artifact in the same conversation still contained a recoverable source.

## Source continuity architecture

1. Large source text is stored in a private browser IndexedDB source vault.
2. Conversation history stores only a compact preview and a durable source reference, avoiding localStorage quota failures.
3. Artifact creation hydrates the full source from the source vault before source resolution.
4. A capability-token-protected backend endpoint can recover the original source snapshot from a completed artifact.
5. When the old snapshot itself contains only a compact-preview marker, the endpoint falls back to the canonical stored artifact-version source.
6. Artifact creation automatically attempts recovery before showing a clarification or failure state.

## Security

- Artifact source recovery requires the existing private artifact capability token.
- Source responses use private no-store headers.
- No source content is placed in URLs.
- IndexedDB data remains browser-local.

## Verification

- Backend suite: 26 tests plus 4 subtests.
- Frontend artifact suite: 6 tests.
- Compact-preview gap detection tested.
- Hydrated browser-source behavior tested.
- Artifact-version fallback recovery tested.
- TypeScript syntax validation passed.
