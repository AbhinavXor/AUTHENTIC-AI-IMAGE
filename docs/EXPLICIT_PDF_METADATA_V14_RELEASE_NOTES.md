# Explicit PDF Metadata V14

## Purpose

V14 makes visible and embedded PDF metadata explicit-only. The renderer no longer invents cover dates, document-type labels, statistics panels, default subtitles, running headers, footers, product branding, or prompt directives in document titles.

## Defaults

- Branding: none
- Cover date: off
- Cover statistics: off
- Cover document label: off
- Default subtitle: off
- Running header: off
- Footer/page numbers: off
- Automatic PDF creation/modification timestamps: removed

## Natural-language opt-in

The user may explicitly request:

- current date
- subtitle
- page numbers
- running headers
- title in footer
- cover metrics/document statistics
- document type label
- branding mode

## Title isolation

Prompts such as:

`Create an unbranded executive report about university AI automation. Include: executive summary, operational workflow analysis...`

produce the document title:

`University AI Automation`

Requested sections remain in the body but are not copied into the title.
