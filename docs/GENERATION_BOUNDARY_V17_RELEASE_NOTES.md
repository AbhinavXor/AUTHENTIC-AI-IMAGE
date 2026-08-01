# Authentic AI — Generation Boundary V17

## Root cause

The source splitter sanitized the complete pasted payload before locating the
final generation-instruction boundary. Sanitization removed the marker heading
but left the instruction body inside the authoritative source. The deterministic
organizer then preserved those instructions, and the structural quality gate
correctly rejected the result as leaked production directives and placeholder
content.

## Resolution

- Generation boundaries are detected before general source sanitization.
- Plain and Markdown headings such as `FINAL PDF GENERATION INSTRUCTION` and
  related PDF/document/artifact creation markers are supported.
- Only the content before the boundary is treated as authoritative document body.
- The instruction tail remains available as control instructions but can never be
  printed into the document.
- Final composed Markdown receives a defense-in-depth cleanup before parsing.
- Provider placeholder lines such as `[insert chart here]` are removed before
  structural validation.
- Existing source routing, layout selection, branding, metadata, revision, and
  large-source storage behavior remain unchanged.
