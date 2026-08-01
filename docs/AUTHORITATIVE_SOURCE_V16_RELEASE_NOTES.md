# Authentic AI — Authoritative Source Routing V16

## Problem fixed

A large pasted source could contain ordinary narrative phrases such as
"previous decisions", "earlier records", "the conversation", "above", or
"same content". The artifact source resolver previously interpreted any one
of those words as a request to use an older chat response. In a new chat,
that produced the incorrect clarification:

> What should the document be about?

This happened even though the complete document source was present in the
same submission.

## Resolution

- Substantial pasted content is classified before prior-response references.
- A source of at least 1,200 characters or 14 non-empty lines is treated as
  authoritative explicit source content.
- Incidental reference words inside the source cannot replace it with older
  conversation content.
- Large source content is preserved in the explicit source snapshot.
- Concise commands such as "Create a PDF from the previous answer" continue
  to resolve the previous assistant response.
- Home includes a second safety guard so a substantial current submission
  cannot fall through to a missing-topic clarification.

## Compatibility

V16 preserves Creation Routing V15, Explicit Metadata V14, Adaptive PDF
Layout V13, large-source storage, artifact revision, and existing backend
APIs.
