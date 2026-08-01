import type {
  ArtifactJobCreateRequest,
} from '../types/artifact-jobs'
import type {
  ArtifactIntentDecision,
} from '../types/artifact-intent'

import type {
  ArtifactFormat,
  ArtifactSourceReference,
  ArtifactSourceSnapshot,
} from '../types/artifacts'

import {
  artifactPromptMode,
  compactArtifactInstruction,
  detectArtifactPresentationTier,
  selectArtifactProfile,
} from './artifactPromptProfile'

import {
  cloneChatArtifactSettings,
  type ChatArtifactSettings,
  type ChatArtifactTrigger,
} from '../types/chat-artifacts'


export interface DetectedChatArtifactIntent {
  trigger: ChatArtifactTrigger
  settings: ChatArtifactSettings
}


const creationPatterns: RegExp[] = [
  /\bcreate\b/i,
  /\bmake\b/i,
  /\bgenerate\b/i,
  /\bprepare\b/i,
  /\bproduce\b/i,
  /\bdraft\b/i,
  /\bexport\b/i,
  /\bconvert\b/i,

  /\bbana\s*do\b/i,
  /\bbanado\b/i,
  /\bbana\s*de\b/i,
  /\bbanade\b/i,
  /\bbana\s*kar\s*do\b/i,
  /\bbanakar\s*do\b/i,
  /\bbana\s*ke\s*do\b/i,
  /\bbanake\s*do\b/i,
  /\bbanao\b/i,
  /\bbanaiye\b/i,

  /\btaiyar\s*karo\b/i,
  /\btaiyar\s*kar\s*do\b/i,
  /\bready\s*kar\s*do\b/i,

  /\bgive\s+me\b/i,
  /\bmujhe\b[\s\S]{0,80}\bchahiye\b/i,
]


const explanationPatterns: RegExp[] = [
  /\bhow\s+to\s+(?:create|make|generate)\b/i,
  /\bhow\s+(?:do|can)\s+(?:i|we)\b/i,
  /\bkaise\s+(?:banaye|banana|banate|banta)\b/i,
  /\bwhat\s+is\s+(?:a\s+)?(?:pdf|docx|pptx)\b/i,
  /\b(?:pdf|docx|pptx)\s+kya\s+hai\b/i,
]


const formatPatterns:
  Array<{
    format: ArtifactFormat
    patterns: RegExp[]
  }> = [
    {
      format: 'pdf',
      patterns: [
        /\bpdf\b/i,
        /\bportable\s+document\b/i,
      ],
    },
    {
      format: 'docx',
      patterns: [
        /\bdocx\b/i,
        /\bword\s+document\b/i,
        /\bms\s+word\b/i,
        /\beditable\s+document\b/i,
      ],
    },
    {
      format: 'pptx',
      patterns: [
        /\bpptx\b/i,
        /\bpower\s*point\b/i,
        /\bpowerpoint\b/i,
        /\bpresentation\b/i,
        /\bslide\s+deck\b/i,
        /\bslides?\b/i,
      ],
    },
  ]


function matchesAny(
  value: string,
  patterns: RegExp[],
): boolean {
  return patterns.some(
    (pattern) =>
      pattern.test(value),
  )
}


function detectFormat(
  message: string,
): ArtifactFormat | null {
  for (
    const formatEntry
    of formatPatterns
  ) {
    if (
      matchesAny(
        message,
        formatEntry.patterns,
      )
    ) {
      return formatEntry.format
    }
  }

  return null
}


function detectTone(
  message: string,
): ChatArtifactSettings['tone'] {
  if (
    /\bexecutive\b/i.test(message)
  ) {
    return 'executive'
  }

  if (
    /\btechnical\b/i.test(message)
  ) {
    return 'technical'
  }

  if (
    /\bacademic\b/i.test(message)
  ) {
    return 'academic'
  }

  if (
    /\bsimple(?:\s+language)?\b/i
      .test(message) ||
    /\beasy\s+language\b/i
      .test(message) ||
    /\bsimplest\s+english\b/i
      .test(message)
  ) {
    return 'simple'
  }

  return 'professional'
}


function detectLength(
  message: string,
): ChatArtifactSettings['length'] {
  if (
    /\bbrief\b/i.test(message) ||
    /\bshort\b/i.test(message) ||
    /\bconcise\b/i.test(message) ||
    /\bchhota\b/i.test(message)
  ) {
    return 'brief'
  }

  if (
    /\bdetailed\b/i.test(message) ||
    /\bcomprehensive\b/i.test(message) ||
    /\bcomplete\b/i.test(message) ||
    /\bfull\b/i.test(message) ||
    /\bdeep\b/i.test(message) ||
    /\bpoora\b/i.test(message) ||
    /\bproper\b/i.test(message)
  ) {
    return 'detailed'
  }

  return 'standard'
}


function detectLayoutFamily(
  message: string,
): ChatArtifactSettings['layoutFamily'] {
  const patterns: Array<[
    ChatArtifactSettings['layoutFamily'],
    RegExp,
  ]> = [
    ['executive_report', /\b(?:executive report|executive brief|board report|leadership report)\b/i],
    ['technical_spec', /\b(?:technical specification|technical spec|engineering specification)\b/i],
    ['research_paper', /\b(?:research paper|research report|literature review)\b/i],
    ['proposal_document', /\b(?:business proposal|project proposal|statement of work)\b/i],
    ['academic_textbook', /\b(?:textbook|academic notes?|study guide|worked examples?|theorem|proof|mathematics|calculus|algebra)\b/i],
    ['case_study', /\b(?:case study|customer story|challenge and solution|lessons learned)\b/i],
    ['data_report', /\b(?:data report|analytics|dashboard|benchmark|metrics?|kpi|statistical|survey results?)\b/i],
    ['executive_report', /\b(?:executive|board|leadership|management|strategic|operational analysis|risk assessment)\b/i],
    ['technical_spec', /\b(?:architecture|engineering|api|implementation|system design|runbook)\b/i],
    ['proposal_document', /\b(?:proposal|business case|project plan|pitch|budget|timeline)\b/i],
    ['research_paper', /\b(?:methodology|abstract|evidence review)\b/i],
    ['modern_summary', /\b(?:minimal|modern summary|one[- ]?pager|concise brief)\b/i],
  ]

  for (const [family, pattern] of patterns) {
    if (pattern.test(message)) {
      return family
    }
  }

  return 'auto'
}

function detectBrandingMode(
  message: string,
): ChatArtifactSettings['brandingMode'] {
  if (/\b(?:no branding|unbranded|without (?:a )?(?:logo|brand)|logo hata|name hata|branding hata)\b/i.test(message)) {
    return 'none'
  }
  if (/\b(?:title[- ]page branding|branding on (?:the )?cover|logo only on (?:the )?cover)\b/i.test(message)) {
    return 'title_only'
  }
  if (/\bsubtle branding\b/i.test(message)) {
    return 'subtle'
  }
  if (/\bfull branding\b/i.test(message)) {
    return 'full'
  }
  return 'none'
}

function detectVisualDensity(
  message: string,
): ChatArtifactSettings['visualDensity'] {
  if (/\b(?:compact|dense)\b/i.test(message)) {
    return 'compact'
  }
  if (/\b(?:spacious|airy|lots of whitespace)\b/i.test(message)) {
    return 'spacious'
  }
  if (/\bbalanced\b/i.test(message)) {
    return 'balanced'
  }
  return 'auto'
}

function detectLanguage(
  message: string,
): string {
  if (
    /\bhinglish\b/i.test(message)
  ) {
    return 'Hinglish'
  }

  if (
    /\bhindi\b/i.test(message) ||
    /हिंदी/.test(message)
  ) {
    return 'Hindi'
  }

  if (
    /\benglish\b/i.test(message)
  ) {
    return 'English'
  }

  return 'English'
}


export function detectChatArtifactIntent(
  message: string,
): DetectedChatArtifactIntent | null {
  const normalized =
    message.trim()

  if (!normalized) {
    return null
  }

  const format =
    detectFormat(normalized)

  if (!format) {
    return null
  }

  if (
    matchesAny(
      normalized,
      explanationPatterns,
    )
  ) {
    return null
  }

  if (
    !matchesAny(
      normalized,
      creationPatterns,
    )
  ) {
    return null
  }

  return createChatArtifactIntent(
    normalized,
    format,
  )
}


export function createChatArtifactIntent(
  message: string,
  format: ArtifactFormat,
): DetectedChatArtifactIntent {
  const normalized = message.trim()

  const settings =
    cloneChatArtifactSettings()

  settings.enabled = true
  settings.format = format
  settings.tone =
    detectTone(normalized)
  settings.length =
    detectLength(normalized)
  settings.language =
    detectLanguage(normalized)
  settings.layoutFamily =
    detectLayoutFamily(normalized)
  settings.brandingMode =
    detectBrandingMode(normalized)
  settings.visualDensity =
    detectVisualDensity(normalized)
  Object.assign(
    settings,
    detectExplicitMetadata(normalized),
  )

  return {
    trigger: 'automatic',
    settings,
  }
}


export function createChatArtifactIntentFromDecision(
  message: string,
  decision: ArtifactIntentDecision | null,
): DetectedChatArtifactIntent | null {
  if (
    decision?.action !== 'create' ||
    !decision.format ||
    decision.confidence < 0.62
  ) {
    return null
  }

  return createChatArtifactIntent(
    message,
    decision.format,
  )
}


function detectExplicitMetadata(
  message: string,
): Pick<
  ChatArtifactSettings,
  | 'headerMode'
  | 'footerMode'
  | 'includeCoverDate'
  | 'includeCoverProfile'
  | 'includeDocumentLabel'
  | 'includeCoverSubtitle'
> {
  const noDate = /\b(?:no date|without (?:a )?date|remove (?:the )?date|date mat|date hata)\b/i.test(message)
  const includeDate = !noDate && /\b(?:include|show|add|display|print|with)\s+(?:the\s+)?(?:current\s+)?date\b|\bdated document\b/i.test(message)
  const includeProfile = /\b(?:document statistics|cover metrics|section count|figure count|table count|equation count)\b/i.test(message)
  const includeDocumentLabel = /\b(?:document type label|cover label|show (?:the )?(?:report|document) type)\b/i.test(message)
  const includeCoverSubtitle = /\b(?:include|show|add|display|with)\s+(?:a\s+)?subtitle\b/i.test(message)
  const runningHeader = /\b(?:running header|section header|page header)\b/i.test(message)
  const titleFooter = /\b(?:title in (?:the )?footer|footer with (?:the )?title)\b/i.test(message)
  const pageNumbers = /\b(?:page numbers?|numbered pages?|paginate)\b/i.test(message)

  return {
    headerMode: runningHeader ? 'running_section' : 'none',
    footerMode: titleFooter
      ? 'page_number_and_title'
      : pageNumbers
        ? 'page_number'
        : 'none',
    includeCoverDate: includeDate,
    includeCoverProfile: includeProfile,
    includeDocumentLabel,
    includeCoverSubtitle,
  }
}


function optionalText(
  value: string,
): string | undefined {
  const normalized =
    value.trim()

  return normalized || undefined
}


export function buildChatArtifactJobRequest(
  prompt: string,
  settings: ChatArtifactSettings,
  sourceSnapshot?: ArtifactSourceSnapshot,
  sourceReference?: ArtifactSourceReference,
): ArtifactJobCreateRequest {
  const hasSeparateSource = Boolean(
    sourceReference
    || sourceSnapshot?.content,
  )

  return {
    prompt: compactArtifactInstruction(
      prompt,
      hasSeparateSource,
    ),
    format: settings.format,
    source_snapshot: sourceSnapshot,
    source_ref: sourceReference,
    profile_id: selectArtifactProfile(
      prompt,
      sourceSnapshot?.kind,
    ),
    prompt_mode: artifactPromptMode(
      prompt,
      hasSeparateSource,
    ),
    presentation_tier:
      detectArtifactPresentationTier(
        prompt,
      ),
    document_type:
      settings.format === 'pptx'
        ? 'presentation'
        : 'professional_report',
    idempotency_key:
      crypto.randomUUID(),

    title:
      optionalText(settings.title),

    subtitle:
      optionalText(settings.subtitle),

    author:
      optionalText(settings.author),

    filename:
      optionalText(settings.filename),

    tone: settings.tone,
    length: settings.length,

    language:
      settings.language.trim()
      || 'English',

    layout_family: settings.layoutFamily,
    branding_mode: settings.brandingMode,
    visual_density: settings.visualDensity,
    header_mode: settings.headerMode,
    footer_mode: settings.footerMode,
    include_table_of_contents:
      settings.includeTableOfContents,
    include_section_openers:
      settings.includeSectionOpeners,
    include_cover_date:
      settings.includeCoverDate,
    include_cover_profile:
      settings.includeCoverProfile,
    include_document_label:
      settings.includeDocumentLabel,
    include_cover_subtitle:
      settings.includeCoverSubtitle,

    include_executive_summary:
      settings.includeExecutiveSummary,

    include_table:
      settings.includeTable,

    include_recommendations:
      settings.includeRecommendations,

    include_conclusion:
      settings.includeConclusion,
  }
}
