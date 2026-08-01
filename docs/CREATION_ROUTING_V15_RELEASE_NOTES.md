# Authentic AI — Creation Routing V15

Creation Routing V15 fixes a precedence defect where a long source prompt containing production instructions such as `include`, `remove`, `final filename`, and `PDF` could be misclassified as a revision of an existing artifact.

## Behaviour

- Explicit PDF, DOCX, and PPTX creation always takes precedence over rename/revise/convert actions.
- Large pasted source documents are never treated as revision commands merely because their instructions mention removing branding, including sections, or choosing a filename.
- Genuine concise revision commands still work, including `Remove the watermark from this PDF` and `Add a comparison table and create a new version`.
- The full source proceeds into the existing large-source vault and artifact generation pipeline.
- No backend, PDF renderer, layout, branding, or metadata behaviour is changed.
