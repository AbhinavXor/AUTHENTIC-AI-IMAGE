import type {
  ArtifactFormat,
} from '../types/artifacts'

export type ArtifactCommandType =
  | 'create'
  | 'rename'
  | 'revise'
  | 'convert'
  | 'duplicate'
  | 'delete'
  | 'restore'
  | 'history'
  | 'none'

export interface ArtifactCommand {
  type: ArtifactCommandType
  raw: string
  format?: ArtifactFormat
  filename?: string
  instruction?: string
  version?: number
  confidence: number
}

const formatPatterns:
  Array<{
    format: ArtifactFormat
    pattern: RegExp
  }> = [
    {
      format: 'pdf',
      pattern: /\bpdf\b/i,
    },
    {
      format: 'docx',
      pattern:
        /\b(?:docx|word\s+document|editable\s+document)\b/i,
    },
    {
      format: 'pptx',
      pattern:
        /\b(?:pptx|power\s*point|presentation|slide\s*deck|slides?)\b/i,
    },
  ]

const createPattern =
  /\b(?:create|make|generate|prepare|produce|export|draft|bana\s*do|banado|bana\s*de|banade|banao|banaiye|taiyar\s*karo|taiyar\s*kar\s*do|ready\s*kar\s*do|turn\s+(?:this|it|the\s+content)\s+into|format\s+(?:this|it|the\s+content)\s+as)\b/i

const professionalDocumentCreationPattern =
  /(?:\bprofessionally?\s+(?:organise|organize|format|prepare|compose)\b[\s\S]{0,220}\b(?:pdf|docx|pptx|document|presentation)\b|\b(?:pdf|docx|pptx|document|presentation)\b[\s\S]{0,120}\b(?:banao|bana\s*do|banado|create|make|generate|prepare)\b)/i

const existingArtifactReferencePattern =
  /\b(?:(?:this|that|latest|last|existing|current|generated|previous)\s+(?:pdf|docx|pptx|file|document|artifact|version)|(?:pdf|docx|pptx|file|document|artifact)\s+(?:above|below|already|again)|new\s+version|updated\s+version|revised\s+version)\b/i

const renamePatterns = [
  /\brename\s+(?:(?:this|the|latest|last|generated)\s+)?(?:(?:pdf|docx|pptx|file|document|presentation)\s+)?(?:as|to)\s+(.+?)\s*$/i,
  /\bchange\s+(?:the\s+)?(?:file\s*name|filename|name)\s+(?:as|to)\s+(.+?)\s*$/i,
  /\b(?:is|iss|ye|yeh)\s*(?:pdf|docx|pptx|file|document|presentation)?\s*(?:ka|ki)?\s*(?:naam|name|filename)\s+(.+?)\s+(?:kar\s*do|rakh\s*do|rakho)\s*$/i,
]

const revisionPattern =
  /\b(?:make\s+(?:it|this|that)|change|update|revise|edit|add|remove|delete\s+the\s+section|shorten|shorter|lengthen|longer|expand|simplify|translate|rewrite|include|exclude|improve|modify|isko|isse|isme|is\s+(?:pdf|document|file))\b/i

const strongRevisionPattern =
  /\b(?:(?:create|make|prepare|generate)\s+(?:a\s+)?(?:new|updated|revised|another)\s+version|new\s+version|updated\s+version|revised\s+version|another\s+version|comparison\s+table|summary\s+table|risk\s+table|add\s+(?:a\s+)?(?:table|section|chart|graph|diagram|page)|remove\s+(?:the\s+)?(?:table|section|chart|graph|diagram|page)|version\s+bana|naya\s+version|new\s+copy\s+with\s+changes)\b/i

const duplicatePattern =
  /\b(?:duplicate|copy|clone)\s+(?:(?:this|the|latest|last)\s+)?(?:pdf|docx|pptx|file|document|artifact)?\b/i

const deletePattern =
  /\b(?:delete|remove|trash)\s+(?:(?:this|the|latest|last)\s+)?(?:pdf|docx|pptx|file|document|artifact)\b/i

const historyPattern =
  /\b(?:version\s+history|show\s+versions|list\s+versions|previous\s+versions|versions\s+dikhao)\b/i

const restorePattern =
  /\b(?:restore|revert|go\s+back\s+to)\s+(?:version\s*)?(\d+)\b/i

function detectFormat(
  value: string,
): ArtifactFormat | undefined {
  return formatPatterns.find(
    ({ pattern }) => pattern.test(value),
  )?.format
}

function cleanFilename(
  value: string,
): string {
  return value
    .trim()
    .replace(/^[`"'“”‘’]+/, '')
    .replace(/[`"'“”‘’]+$/, '')
    .replace(/\s+(?:please|pls)$/i, '')
    .trim()
}

export function routeArtifactCommand(
  message: string,
): ArtifactCommand {
  const raw = message.trim()

  if (!raw) {
    return {
      type: 'none',
      raw,
      confidence: 0,
    }
  }

  for (const pattern of renamePatterns) {
    const match = raw.match(pattern)
    const filename = match?.[1]

    if (filename) {
      return {
        type: 'rename',
        raw,
        filename: cleanFilename(filename),
        confidence: 0.99,
      }
    }
  }

  const restoreMatch =
    raw.match(restorePattern)

  if (restoreMatch?.[1]) {
    return {
      type: 'restore',
      raw,
      version: Number(restoreMatch[1]),
      confidence: 0.98,
    }
  }

  if (historyPattern.test(raw)) {
    return {
      type: 'history',
      raw,
      confidence: 0.98,
    }
  }

  if (duplicatePattern.test(raw)) {
    return {
      type: 'duplicate',
      raw,
      confidence: 0.98,
    }
  }

  if (deletePattern.test(raw)) {
    return {
      type: 'delete',
      raw,
      confidence: 0.98,
    }
  }

  const format = detectFormat(raw)

  if (
    format &&
    /\b(?:convert|export)\b/i.test(raw) &&
    /\b(?:this|it|file|document|artifact|pdf|docx|pptx)\b/i.test(raw)
  ) {
    return {
      type: 'convert',
      raw,
      format,
      confidence: 0.96,
    }
  }

  if (
    format &&
    (
      createPattern.test(raw) ||
      professionalDocumentCreationPattern.test(raw)
    )
  ) {
    return {
      type: 'create',
      raw,
      format,
      confidence: 0.99,
    }
  }

  const commandLead = raw.slice(0, 320)
  const isLongSourceRequest =
    raw.length > 1_200 ||
    raw.split(/\r?\n/).length > 14
  const hasExistingArtifactReference =
    existingArtifactReferencePattern.test(commandLead)
  const isStrongRevision =
    strongRevisionPattern.test(commandLead)
  const isConciseRevision =
    !isLongSourceRequest &&
    revisionPattern.test(commandLead) &&
    /\b(?:it|this|that|pdf|docx|pptx|document|file|artifact|version|table|section|chart|graph|diagram|isko|isme|isse)\b/i.test(commandLead)

  if (
    isStrongRevision ||
    hasExistingArtifactReference ||
    isConciseRevision
  ) {
    return {
      type: 'revise',
      raw,
      instruction: raw,
      confidence: 0.88,
    }
  }

  return {
    type: 'none',
    raw,
    confidence: 0,
  }
}
