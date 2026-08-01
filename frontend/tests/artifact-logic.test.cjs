const test = require('node:test')
const assert = require('node:assert/strict')

const {
  routeArtifactCommand,
} = require('../.test-dist/lib/artifactCommandRouter.js')
const {
  artifactSourceHasCompactPreviewGap,
  isArtifactSourceRecoveryRequest,
  resolveArtifactSource,
  selectRecoveredArtifactSource,
} = require('../.test-dist/lib/artifactSourceResolver.js')
const {
  resolveArtifactReference,
} = require('../.test-dist/lib/artifactReferenceResolver.js')
const {
  buildChatArtifactJobRequest,
  createChatArtifactIntentFromDecision,
  detectChatArtifactIntent,
} = require('../.test-dist/lib/chatArtifactIntent.js')
const {
  artifactPromptMode,
  compactArtifactInstruction,
  detectArtifactPresentationTier,
  selectArtifactProfile,
} = require('../.test-dist/lib/artifactPromptProfile.js')

const {
  compactPreviewMatchesSource,
  createCompactArtifactSourcePreview,
  extractArtifactSourceReference,
  hydrateArtifactSourceMessages,
  recoverArtifactSourcePrompt,
  storeArtifactSource,
} = require('../.test-dist/services/artifact-source-vault.js')


test('routes English and Hinglish artifact commands', () => {
  const englishCreate = routeArtifactCommand(
    'Create a professional PDF about the Serenya logo',
  )
  assert.equal(englishCreate.type, 'create')
  assert.equal(englishCreate.format, 'pdf')

  const create = routeArtifactCommand(
    'is answer ka docx bana do',
  )
  assert.equal(create.type, 'create')
  assert.equal(create.format, 'docx')

  const rename = routeArtifactCommand(
    'rename this PDF to Final Report.pdf',
  )
  assert.equal(rename.type, 'rename')
  assert.equal(rename.filename, 'Final Report.pdf')

  assert.equal(
    routeArtifactCommand(
      'make this document shorter',
    ).type,
    'revise',
  )


  assert.equal(
    routeArtifactCommand(
      'Add a comparison table and create a new version.',
    ).type,
    'revise',
  )

  assert.equal(
    routeArtifactCommand(
      'Add the graph and prepare an updated version.',
    ).type,
    'revise',
  )

  const convert = routeArtifactCommand(
    'convert this document to PPTX',
  )
  assert.equal(convert.type, 'convert')
  assert.equal(convert.format, 'pptx')

  assert.equal(
    routeArtifactCommand(
      'show version history',
    ).type,
    'history',
  )

  const restore = routeArtifactCommand(
    'restore version 2',
  )
  assert.equal(restore.type, 'restore')
  assert.equal(restore.version, 2)
})


test('maps an AI semantic decision into automatic artifact generation', () => {
  const detected = createChatArtifactIntentFromDecision(
    'Mera college project submission ke liye final ready kar do.',
    {
      action: 'create',
      format: 'pdf',
      confidence: 0.94,
      reason: 'Submission-ready deliverable requested.',
      source: 'ai',
    },
  )
  assert.ok(detected)
  assert.equal(detected.trigger, 'automatic')
  assert.equal(detected.settings.format, 'pdf')
  assert.equal(detected.settings.enabled, true)

  assert.equal(
    createChatArtifactIntentFromDecision(
      'Explain recursion.',
      {
        action: 'none',
        format: null,
        confidence: 0.99,
        reason: 'Ordinary chat.',
        source: 'deterministic',
      },
    ),
    null,
  )
})


test('packages an attached PDF redesign as a compact profile request', () => {
  const prompt = (
    'Redesign the attached PDF as a professional BTech final-year project report.\n'
    + 'Preserve all useful content, equations, tables, graphs, and diagrams.\n'
    + 'Do not add branding, watermark, date, headers, or footers.\n'
  ).repeat(180)
  const settings = detectChatArtifactIntent(
    `${prompt}\nGenerate the final PDF.`,
  ).settings
  const reference = {
    source_id: 'a'.repeat(32),
    access_token: 'b'.repeat(43),
  }
  const request = buildChatArtifactJobRequest(
    prompt,
    settings,
    {
      kind: 'uploaded_file',
      summary: 'Uploaded BTech project PDF',
      message_ids: [],
      attachment_names: ['project.pdf'],
      confidence: 1,
    },
    reference,
  )

  assert.equal(request.profile_id, 'redesign_existing')
  assert.equal(request.presentation_tier, 'professional')
  assert.equal(request.prompt_mode, 'compact')
  assert.deepEqual(request.source_ref, reference)
  assert.equal(request.source_snapshot.content, undefined)
  assert.ok(request.prompt.length <= 2400)
  assert.equal(selectArtifactProfile(prompt, 'uploaded_file'), 'redesign_existing')
  assert.equal(artifactPromptMode(prompt, true), 'compact')
  assert.ok(compactArtifactInstruction(prompt, true).length <= 2400)
})


test('treats a generic professional request for an uploaded PDF as redesign', () => {
  assert.equal(
    selectArtifactProfile(
      'Create a professional PDF of this PDF.',
      'uploaded_file',
    ),
    'redesign_existing',
  )
  assert.equal(
    selectArtifactProfile(
      'Is uploaded file ko polished final-ready document banao.',
      'uploaded_file',
    ),
    'redesign_existing',
  )
})


test('sends distinct presentation tiers for normal and premium PDF requests', () => {
  assert.equal(
    detectArtifactPresentationTier('Is content ka PDF bana do.'),
    'standard',
  )
  assert.equal(
    detectArtifactPresentationTier('Create a professional PDF.'),
    'professional',
  )
  assert.equal(
    detectArtifactPresentationTier('Isko best professional final-ready PDF banao.'),
    'premium',
  )

  const settings = detectChatArtifactIntent(
    'Isko best professional final-ready PDF banao.',
  ).settings
  const request = buildChatArtifactJobRequest(
    'Isko best professional final-ready PDF banao.',
    settings,
  )
  assert.equal(request.presentation_tier, 'premium')
})


test('treats a large source plus final PDF instructions as creation, not revision', () => {
  const source = [
    '# AI-Enabled University Operations',
    '',
    '## Executive Overview',
    'Universities operate through complex academic and administrative processes.',
    '',
    '## Final PDF Generation Instruction',
    'Is complete content ko professionally organise karo aur polished PDF banao.',
    'Include a title page, contents, tables, charts, and conclusion.',
    'Remove logo, watermark, author, date, headers, footers, and page numbers.',
    'Prompt instructions ko title ya body me include mat banana.',
    'Final filename: AI-Enabled-University-Operations.pdf',
  ].join('\n') + '\n' + 'Detailed authoritative source paragraph. '.repeat(80)

  const routed = routeArtifactCommand(source)
  assert.equal(routed.type, 'create')
  assert.equal(routed.format, 'pdf')

  const detected = detectChatArtifactIntent(source)
  assert.ok(detected)
  assert.equal(detected.settings.format, 'pdf')
})

test('does not interpret incidental instructions inside a long source as artifact revision', () => {
  const source = [
    '# Long source document',
    'Include tables where useful.',
    'Remove unnecessary visual noise.',
    'The source discusses document sections and graphs.',
  ].join('\n') + '\n' + 'Authoritative source material. '.repeat(100)

  assert.equal(
    routeArtifactCommand(source).type,
    'none',
  )

  assert.equal(
    routeArtifactCommand('Remove the watermark from this PDF.').type,
    'revise',
  )
})

test('treats incidental prior-reference words inside a large pasted source as source content', () => {
  const source = [
    '# AI-Enabled University Operations',
    '',
    'Different staff members may interpret the same policy differently.',
    'The assistant should present the applicable rule, required evidence, and previous decisions.',
    'Earlier operational records may be reviewed during governance analysis.',
    'The conversation history must not replace this authoritative source.',
    'Use the complete content above only as document material.',
    '',
    'FINAL PDF GENERATION INSTRUCTION',
    'Is complete content ko professionally organise karke PDF banao.',
    'Final filename: AI-Enabled-University-Operations.pdf',
  ].join('\n') + '\n' + 'Detailed university operations source paragraph. '.repeat(100)

  const resolved = resolveArtifactSource(
    source,
    [],
  )

  assert.equal(
    resolved.requiresClarification,
    false,
  )
  assert.equal(
    resolved.snapshot?.kind,
    'explicit_prompt',
  )
  assert.equal(
    resolved.snapshot?.content,
    source.trim(),
  )
  assert.match(
    resolved.prompt,
    /complete explicit source snapshot/,
  )
})

test('preserves a durable source reference inside compact chat previews', () => {
  const source = [
    '# AI-Enabled University Operations',
    '',
    'Executive source content. '.repeat(900),
    '',
    'FINAL PDF GENERATION INSTRUCTION',
    'Create the requested professional PDF.',
    'Final filename: AI-Enabled-University-Operations.pdf',
  ].join('\n')

  const sourceId = 'artifact-source:test-source-1'
  const preview = createCompactArtifactSourcePreview(
    source,
    sourceId,
  )

  assert.match(
    preview,
    /Large source preserved securely for document generation/,
  )
  assert.equal(
    extractArtifactSourceReference(preview),
    sourceId,
  )
  assert.equal(
    compactPreviewMatchesSource(preview, source),
    true,
  )
})

test('recovers a copied compact preview from the durable source vault', async () => {
  const source = (
    '# Durable Source Recovery\n\n'
    + 'Complete authoritative content. '.repeat(1400)
    + '\n\nFINAL PDF GENERATION INSTRUCTION\n'
    + 'Create a professional PDF.\n'
    + 'Final filename: Durable-Source-Recovery.pdf'
  )
  const sourceId = 'artifact-source:durable-recovery'

  await storeArtifactSource(sourceId, source)

  const preview = createCompactArtifactSourcePreview(
    source,
    sourceId,
  )
  const recovered = await recoverArtifactSourcePrompt(preview)

  assert.ok(recovered)
  assert.equal(recovered.sourceId, sourceId)
  assert.equal(recovered.content, source.trim())
  assert.equal(recovered.recovered, true)

  const intent = detectChatArtifactIntent(recovered.content)
  const resolved = resolveArtifactSource(recovered.content, [])

  assert.ok(intent)
  assert.equal(intent.settings.format, 'pdf')
  assert.equal(resolved.requiresClarification, false)
  assert.equal(resolved.snapshot?.kind, 'explicit_prompt')
})

test('hydrates an older compact chat message even when it has no source reference', async () => {
  const source = (
    '# Legacy Compact Preview\n\n'
    + 'Preserved source body. '.repeat(1500)
    + '\n\nFINAL PDF GENERATION INSTRUCTION\n'
    + 'Create a PDF.\n'
    + 'Final filename: Legacy-Preview.pdf'
  )
  const sourceId = 'artifact-source:legacy-preview'

  await storeArtifactSource(sourceId, source)

  const oldPreview = createCompactArtifactSourcePreview(source)
  const hydrated = await hydrateArtifactSourceMessages([
    {
      id: 'legacy-message',
      role: 'user',
      content: oldPreview,
    },
  ])

  assert.equal(hydrated[0].artifactSourceRef, sourceId)
  assert.equal(hydrated[0].artifactSourceContent, source.trim())
})

test('recovers compact previews by stable beginning and ending content', () => {
  const source = (
    '# Long Research Document\n\n'
    + 'Authoritative research paragraph. '.repeat(1200)
    + '\n\nFINAL PDF GENERATION INSTRUCTION\n'
    + 'Create a professional research PDF.\n'
    + 'Final filename: Research-Document.pdf'
  )

  const preview = createCompactArtifactSourcePreview(source)

  assert.equal(
    compactPreviewMatchesSource(preview, source),
    true,
  )
  assert.equal(
    compactPreviewMatchesSource(
      preview,
      source.replace('Research-Document.pdf', 'Different.pdf'),
    ),
    false,
  )
})

test('still resolves a concise previous-answer request from conversation context', () => {
  const priorConversation = [
    {
      id: 'user-prior',
      role: 'user',
      content: 'Explain university AI automation.',
    },
    {
      id: 'assistant-prior',
      role: 'assistant',
      content: (
        'University AI automation can improve admissions, registration, '
        + 'student support, governance, and operational reporting while '
        + 'preserving human authority for sensitive decisions.'
      ),
    },
  ]

  const resolved = resolveArtifactSource(
    'Create a PDF from the previous answer.',
    priorConversation,
  )

  assert.equal(
    resolved.requiresClarification,
    false,
  )
  assert.equal(
    resolved.snapshot?.kind,
    'previous_response',
  )
  assert.match(
    resolved.snapshot?.content ?? '',
    /University AI automation/,
  )
})

test('infers unbranded content-aware document layout settings', () => {
  const detected = detectChatArtifactIntent(
    'Create an unbranded academic textbook PDF with worked examples and spacious layout.',
  )
  assert.ok(detected)
  assert.equal(detected.settings.layoutFamily, 'academic_textbook')
  assert.equal(detected.settings.brandingMode, 'none')
  assert.equal(detected.settings.visualDensity, 'spacious')

  const request = buildChatArtifactJobRequest(
    'Create the PDF.',
    detected.settings,
  )
  assert.equal(request.layout_family, 'academic_textbook')
  assert.equal(request.branding_mode, 'none')
  assert.equal(request.footer_mode, 'none')
  assert.equal(request.include_table_of_contents, true)
})


test('keeps cover metadata off unless the prompt explicitly requests it', () => {
  const clean = detectChatArtifactIntent(
    'Create an unbranded executive report PDF about university AI automation. Include an executive summary and operational workflow analysis.',
  )
  assert.ok(clean)
  assert.equal(clean.settings.layoutFamily, 'executive_report')
  assert.equal(clean.settings.footerMode, 'none')
  assert.equal(clean.settings.includeCoverDate, false)
  assert.equal(clean.settings.includeCoverProfile, false)
  assert.equal(clean.settings.includeDocumentLabel, false)
  assert.equal(clean.settings.includeCoverSubtitle, false)

  const explicit = detectChatArtifactIntent(
    'Create an executive report PDF about university AI automation with a subtitle, include the current date and page numbers.',
  )
  assert.ok(explicit)
  assert.equal(explicit.settings.includeCoverDate, true)
  assert.equal(explicit.settings.includeCoverSubtitle, true)
  assert.equal(explicit.settings.footerMode, 'page_number')
})

const conversation = [
  {
    id: 'user-1',
    role: 'user',
    content: 'Explain the Serenya logo and redesign options.',
  },
  {
    id: 'assistant-1',
    role: 'assistant',
    content: (
      'The Serenya logo uses a glossy sphere, an S-shaped wave, '
      + 'and violet, magenta, cyan, and blue gradients. A professional '
      + 'redesign should preserve the motion while creating a simplified '
      + 'vector master for small interfaces and dark mode.'
    ),
  },
]

test('resolves authoritative sources without generic topic substitution', () => {
  const generic = resolveArtifactSource(
    'create a pdf',
    conversation,
  )
  assert.equal(generic.requiresClarification, false)
  assert.equal(generic.snapshot?.kind, 'previous_response')
  assert.match(generic.snapshot?.content ?? '', /Serenya logo/)
  assert.doesNotMatch(
    generic.snapshot?.content ?? '',
    /Your PDF is ready/,
  )

  const missing = resolveArtifactSource(
    'create a pdf',
    [],
  )
  assert.equal(missing.requiresClarification, true)
  assert.match(missing.clarification ?? '', /What should/)

  const explicit = resolveArtifactSource(
    'Create a PDF about hospital discharge coordination',
    conversation,
  )
  assert.equal(explicit.requiresClarification, false)
  assert.equal(explicit.snapshot?.kind, 'explicit_prompt')
  assert.match(
    explicit.snapshot?.summary ?? '',
    /hospital discharge coordination/,
  )
})



test('stores a very large explicit source once and sends a compact instruction', () => {
  const source = (
    'Detailed mathematics source with equations and examples. '
  ).repeat(2_000)
  const prompt = `${source}\n\nOrganise this and create a professional PDF.`

  const resolved = resolveArtifactSource(
    prompt,
    [],
  )

  assert.equal(resolved.requiresClarification, false)
  assert.ok(
    resolved.prompt.length < 500,
  )
  assert.match(
    resolved.prompt,
    /complete explicit source snapshot/,
  )
  assert.equal(resolved.snapshot?.kind, 'explicit_prompt')
  assert.equal(
    resolved.snapshot?.content,
    prompt,
  )
})

test('selects a matching recovered source instead of the newest unrelated artifact', () => {
  const previewMessage = {
    id: 'mathematics-source-message',
    role: 'user',
    content: [
      'MATHEMATICS PDF TEST — CALCULUS, ALGEBRA, PROBABILITY, AND MODELLING',
      '',
      '[Large source preserved for document generation: 20,000 middle characters hidden in chat preview]',
      '',
      'Preserve all equations, worked examples, graphs, glossary and verification.',
    ].join('\n'),
  }
  const prompt = (
    'Complete stored authoritative mathematics source ko recover karo '
    + 'and create a PDF with equations, worked examples, graphs and glossary.'
  )
  const unrelated = {
    reference: {
      messageId: 'newer-university-card',
      artifact: record(
        'university-artifact',
        'University-AI-Automation.pdf',
        'pdf',
      ),
    },
    source: {
      artifact_id: 'university-artifact',
      version: 1,
      title: 'University AI Automation',
      filename: 'University-AI-Automation.pdf',
      kind: 'previous_response',
      summary: 'Operational automation benefits and risks',
      content: 'University admissions, governance, operating cost and service availability.',
      message_ids: [],
      attachment_names: [],
      confidence: 0.98,
      recovered_from: 'source_snapshot',
    },
  }
  const mathematics = {
    reference: {
      messageId: 'older-mathematics-card',
      artifact: record(
        'mathematics-artifact',
        'Mathematics-Master.pdf',
        'pdf',
      ),
    },
    source: {
      artifact_id: 'mathematics-artifact',
      version: 1,
      title: 'Mathematics: Calculus, Algebra, Probability, and Modelling',
      filename: 'Mathematics-Master.pdf',
      kind: 'explicit_prompt',
      summary: 'Complete mathematics learning source',
      content: (
        'Mathematics chapters with equations, worked examples, '
        + 'calculus, algebra, probability, graphs, glossary and verification.'
      ),
      message_ids: [
        'mathematics-source-message',
      ],
      attachment_names: [],
      confidence: 0.99,
      recovered_from: 'source_snapshot',
    },
  }

  assert.equal(
    isArtifactSourceRecoveryRequest(
      prompt,
    ),
    true,
  )
  assert.equal(
    selectRecoveredArtifactSource(
      prompt,
      [previewMessage],
      [unrelated, mathematics],
    )?.source.artifact_id,
    'mathematics-artifact',
  )
})

test('rejects unrelated recovery candidates when no source lineage or topic matches', () => {
  const selected =
    selectRecoveredArtifactSource(
      'Recover the stored mathematics source with equations and graphs.',
      [],
      [{
        reference: {
          messageId: 'university-card',
          artifact: record(
            'university-artifact',
            'University-AI-Automation.pdf',
            'pdf',
          ),
        },
        source: {
          artifact_id: 'university-artifact',
          version: 1,
          title: 'University AI Automation',
          filename: 'University-AI-Automation.pdf',
          kind: 'previous_response',
          summary: 'Operational automation',
          content: 'Admissions workflow, governance and operating cost.',
          message_ids: [],
          attachment_names: [],
          confidence: 0.98,
          recovered_from: 'source_snapshot',
        },
      }],
    )

  assert.equal(selected, null)
})


test('detects compact-preview source gaps and accepts hydrated full sources', () => {
  const previewMessage = {
    id: 'large-user-source',
    role: 'user',
    content: [
      'Beginning of the mathematics source.',
      '',
      '[Large source preserved for document generation: 20,000 middle characters hidden in chat preview]',
      '',
      'Create a professional PDF.',
    ].join('\n'),
  }

  const unresolved = resolveArtifactSource(
    'create a pdf',
    [previewMessage],
  )

  assert.equal(
    artifactSourceHasCompactPreviewGap(
      unresolved,
      [previewMessage],
    ),
    true,
  )

  const hydratedMessage = {
    ...previewMessage,
    artifactSourceContent: (
      'Complete authoritative mathematics source with equations, examples, warnings and chapters. '
    ).repeat(300),
  }
  const hydrated = resolveArtifactSource(
    'create a pdf',
    [hydratedMessage],
  )

  assert.equal(
    artifactSourceHasCompactPreviewGap(
      hydrated,
      [hydratedMessage],
    ),
    false,
  )
  assert.match(
    hydrated.snapshot?.content ?? '',
    /Complete authoritative mathematics source/,
  )

  const freshExplicit = resolveArtifactSource(
    'Create a PDF about a new hospital operations topic with complete details.',
    [previewMessage],
  )
  assert.equal(
    artifactSourceHasCompactPreviewGap(
      freshExplicit,
      [previewMessage],
    ),
    false,
  )
})

test('keeps recent generated visualizations in artifact source context', () => {
  const chartBlock = `\`\`\`authentic-chart
{"version":"1.0","title":"Automation Savings","estimated":false,"limitations":[],"option":{"xAxis":{"type":"category","data":["Manual","Automated"]},"yAxis":{"type":"value"},"series":[{"name":"Hours","type":"bar","data":[100,35]}]},"table":{"columns":["Mode","Hours"],"rows":[["Manual",100],["Automated",35]]}}
\`\`\``

  const visualConversation = [
    {
      id: 'user-chart',
      role: 'user',
      content: 'Create a graph of manual and automated workload.',
    },
    {
      id: 'assistant-chart',
      role: 'assistant',
      content: `${chartBlock}\n\nAutomation reduces the modeled workload in this comparison.`,
    },
    {
      id: 'user-explain',
      role: 'user',
      content: 'Explain the operational meaning.',
    },
    {
      id: 'assistant-explain',
      role: 'assistant',
      content: 'The comparison indicates that automation can reduce repetitive processing while preserving review for exceptions and controlled decisions.',
    },
  ]

  const resolved = resolveArtifactSource(
    'create a pdf',
    visualConversation,
  )

  assert.equal(resolved.requiresClarification, false)
  assert.match(
    resolved.snapshot?.content ?? '',
    /```authentic-chart/,
  )
  assert.match(
    resolved.snapshot?.content ?? '',
    /Automation Savings/,
  )
  assert.ok(
    (resolved.snapshot?.content ?? '').length <= 15_500,
  )
  assert.equal(
    (resolved.snapshot?.content ?? '')
      .match(/```authentic-chart/g)?.length,
    1,
  )
})

function record(
  artifactId,
  filename,
  format,
) {
  return {
    artifact_id: artifactId,
    access_token: `token-${artifactId}-123456789012345678901234`,
    filename,
    title: filename.replace(/\.[^.]+$/, ''),
    format,
    media_type: 'application/octet-stream',
    size_bytes: 1000,
    sha256: 'a'.repeat(64),
    created_at: '2026-07-27T00:00:00Z',
    updated_at: '2026-07-27T00:00:00Z',
    expires_at: '2026-07-28T00:00:00Z',
    download_url: `/download/${artifactId}`,
    version: 1,
    version_count: 1,
    page_or_slide_count: 2,
    validation: {
      status: 'passed',
      page_or_slide_count: 2,
      error_count: 0,
      warning_count: 0,
      issues: [],
    },
  }
}

const messages = [
  {
    id: 'assistant-zip',
    role: 'assistant',
    content: 'Your PDF bundle is ready.',
    artifact: {
      trigger: 'automatic',
      format: 'zip',
      title: 'Large Mathematics Source',
      filename: 'Large-Mathematics-Source-PDF-Volumes.zip',
      status: 'succeeded',
      progressPercent: 100,
      stage: 'Ready',
      artifact: record(
        'zip-artifact',
        'Large-Mathematics-Source-PDF-Volumes.zip',
        'zip',
      ),
      error: null,
    },
  },
  {
    id: 'assistant-pdf',
    role: 'assistant',
    content: 'Your PDF is ready.',
    artifact: {
      trigger: 'automatic',
      format: 'pdf',
      title: 'Serenya Logo Review',
      filename: 'Serenya-Logo-Review.pdf',
      status: 'succeeded',
      progressPercent: 100,
      stage: 'Ready',
      artifact: record(
        'pdf-artifact',
        'Serenya-Logo-Review.pdf',
        'pdf',
      ),
      error: null,
    },
  },
  {
    id: 'assistant-docx',
    role: 'assistant',
    content: 'Your DOCX is ready.',
    artifact: {
      trigger: 'automatic',
      format: 'docx',
      title: 'Operations Plan',
      filename: 'Operations-Plan.docx',
      status: 'succeeded',
      progressPercent: 100,
      stage: 'Ready',
      artifact: record(
        'docx-artifact',
        'Operations-Plan.docx',
        'docx',
      ),
      error: null,
    },
  },
]

test('resolves the correct artifact by filename, format, or latest reference', () => {
  assert.equal(
    resolveArtifactReference(
      'download the PDF bundle ZIP',
      messages,
    )?.artifact.artifact_id,
    'zip-artifact',
  )

  assert.equal(
    resolveArtifactReference(
      'rename Serenya-Logo-Review.pdf to Final.pdf',
      messages,
    )?.artifact.artifact_id,
    'pdf-artifact',
  )

  assert.equal(
    resolveArtifactReference(
      'convert the PDF to PPTX',
      messages,
    )?.artifact.artifact_id,
    'pdf-artifact',
  )

  assert.equal(
    resolveArtifactReference(
      'rename this file to Final.docx',
      messages,
    )?.artifact.artifact_id,
    'docx-artifact',
  )
})
