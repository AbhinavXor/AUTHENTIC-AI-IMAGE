# Authentic AI - Artifact Recovery V8

## Purpose

Artifact Recovery V8 closes the recovery loop that previously surfaced a
structural-quality error when an older generated artifact contained UI preview
markers, user action text as the title, or internal document-production
instructions.

## Root cause fixed

Older artifact lineages could contain one or more of the following:

- a command such as `Add a Comparison Table and a New Version` stored as H1;
- a compact chat-preview marker embedded in the canonical document body;
- `Document Production Requirements` or equivalent internal instruction
  sections stored as visible document content;
- an original source snapshot and a rendered artifact version with different
  levels of contamination;
- a recovered original source incorrectly labelled as a canonical artifact
  version by the frontend.

The quality validator correctly rejected these outputs, but the system did not
repair the known contamination before validation.

## V8 behavior

1. The source recovery API evaluates both the original source snapshot and the
   stored artifact version.
2. A clean source snapshot remains the first choice.
3. A contaminated snapshot is not preferred over a cleaner canonical artifact
   version.
4. Recovered payloads are sanitized before source planning, composition,
   parsing, rendering, and quality validation.
5. Compact-preview markers are removed even when line wrapping or optional
   brackets differ from the original marker.
6. Internal production sections are removed at any Markdown heading level.
7. Command titles are replaced with a topic-derived professional title.
8. Canonical artifact recovery is deterministic and idempotent; it never calls
   an external model or reorganizes the document a second time.
9. The frontend preserves the actual recovered source kind instead of marking
   every recovered payload as `artifact_version`.
10. A second defensive repair layer runs in the lifecycle service before the
    document IR is parsed.

## Regression coverage

The V8 test suite covers:

- command-title repair;
- multi-line compact-preview marker removal;
- internal production-section removal;
- deterministic canonical recovery;
- idempotent repeated recovery;
- clean source selection over a polluted snapshot;
- PDF rendering after automatic repair;
- preservation of all numbered mathematics chapters;
- no user retry required for known repairable contamination.

## Compatibility

This patch is additive and compatible with the Phase 1-6 artifact domain,
Artifact UX V2, Large Artifacts V3, Source Fidelity V4, Professional Document
V5, Source Continuity V6, and Artifact Reliability V7.
