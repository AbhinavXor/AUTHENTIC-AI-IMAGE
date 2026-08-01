# Authentic AI Large Artifacts V3

## Purpose

Large Artifacts V3 removes the legacy 8,000-character artifact prompt ceiling and adds a bounded, recoverable pipeline for long-form PDF generation.

## Runtime behavior

1. The artifact API accepts up to 2,000,000 prompt characters by default.
2. Long authoritative sources are split at paragraph and fenced-block boundaries into bounded composition chunks.
3. Medium and large requests are composed through ordered multi-pass generation while preserving equations, examples, warnings, tables, and `authentic-chart` visualization blocks.
4. A PDF request whose authoritative source exceeds 260,000 characters is automatically converted into a ZIP containing two to four numbered PDF volumes.
5. Extremely large sources use deterministic preservation mode to avoid provider context overflow or hundreds of external model calls.
6. Each ZIP contains `manifest.json` plus numbered PDF files. Every PDF is reopened and validated before the bundle is marked ready.
7. Large prompts are compacted only in the visible chat transcript. The complete prompt remains the generation source sent to the backend.
8. Client polling windows scale with source size so long jobs are not reported as timed out after the former four-minute window.

## Visualization preservation

Valid fenced `authentic-chart` blocks are carried into the structured document pipeline. Charts are rendered in PDF volumes and are not replaced by plain-text placeholders. ZIP volume balancing assigns chart blocks a higher layout weight so visual-heavy sections are distributed more evenly.

## Default limits

| Setting | Default |
|---|---:|
| Maximum request body | 24 MiB |
| Maximum artifact prompt | 2,000,000 characters |
| Composition chunk target | 9,000 characters |
| Automatic PDF bundle threshold | 260,000 source characters |
| Maximum automatic PDF volumes | 4 |
| Maximum generated artifact source | 2,000,000 characters |
| Maximum generated file | 200 MiB |

These are production safety limits, not a return to the former small-prompt restriction. Sources beyond the configured ceiling should be ingested through a future streamed upload/object-storage path rather than held in one browser request.

## Validation

The release test suite covers:

- prompts larger than 8,000 characters;
- ordered source chunking;
- large explicit prompt preservation in the frontend;
- automatic PDF-to-ZIP conversion;
- structured and unstructured large sources;
- two-to-four volume generation;
- ZIP manifest integrity;
- PDF reopening and output-quality checks;
- graph-source preservation;
- ZIP artifact reference resolution.
