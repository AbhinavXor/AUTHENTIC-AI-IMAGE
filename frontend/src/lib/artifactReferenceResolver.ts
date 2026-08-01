import type {
  ArtifactFormat,
  ArtifactRecord,
} from '../types/artifacts'
import type {
  ConversationMessage,
} from '../types/chat'

export interface ResolvedArtifactReference {
  messageId: string
  artifact: ArtifactRecord
}

interface Candidate extends ResolvedArtifactReference {
  index: number
}

const formatPattern: Record<
  ArtifactFormat,
  RegExp
> = {
  pdf: /\bpdf\b/i,
  docx: /\b(?:docx|word\s+document)\b/i,
  pptx: /\b(?:pptx|power\s*point|presentation|slides?)\b/i,
  zip: /\b(?:zip|pdf\s+bundle|volumes?)\b/i,
}

function candidatesFromMessages(
  messages: ConversationMessage[],
): Candidate[] {
  return messages.flatMap(
    (message, index) => {
      const artifact =
        message.artifact?.artifact

      if (
        message.artifact?.status !==
          'succeeded' ||
        !artifact
      ) {
        return []
      }

      return [{
        messageId: message.id,
        artifact,
        index,
      }]
    },
  )
}

export function listArtifactReferences(
  messages: ConversationMessage[],
): ResolvedArtifactReference[] {
  const seenArtifactIds =
    new Set<string>()

  return candidatesFromMessages(messages)
    .slice()
    .reverse()
    .filter(({ artifact }) => {
      if (
        seenArtifactIds.has(
          artifact.artifact_id,
        )
      ) {
        return false
      }

      seenArtifactIds.add(
        artifact.artifact_id,
      )
      return true
    })
    .map(
      ({ messageId, artifact }) => ({
        messageId,
        artifact,
      }),
    )
}

function normalizedFilenameParts(
  artifact: ArtifactRecord,
): string[] {
  const filename = artifact.filename
    .toLocaleLowerCase()
  const stem = filename.replace(
    /\.(pdf|docx|pptx|zip)$/i,
    '',
  )

  return [
    filename,
    stem,
    artifact.title.toLocaleLowerCase(),
  ].filter(
    (value) => value.length >= 3,
  )
}

export function resolveArtifactReference(
  command: string,
  messages: ConversationMessage[],
): ResolvedArtifactReference | null {
  const candidates =
    candidatesFromMessages(messages)

  if (candidates.length === 0) {
    return null
  }

  const normalized =
    command.toLocaleLowerCase()

  const filenameMatch = candidates
    .slice()
    .reverse()
    .find(
      ({ artifact }) =>
        normalizedFilenameParts(artifact)
          .some(
            (part) =>
              normalized.includes(part),
          ),
    )

  if (filenameMatch) {
    return filenameMatch
  }

  const formatPriority: ArtifactFormat[] = [
    'zip',
    'pptx',
    'docx',
    'pdf',
  ]

  const conversionSourceSegment =
    command.match(
      /\b(?:convert|export)\b([\s\S]*?)\b(?:to|as|into)\b/i,
    )?.[1]

  const sourceFormat =
    conversionSourceSegment
      ? (['zip', 'pdf', 'docx', 'pptx'] as ArtifactFormat[])
          .find(
            (format) =>
              formatPattern[format]
                .test(conversionSourceSegment),
          )
      : undefined

  const requestedFormat =
    sourceFormat ??
    formatPriority.find(
      (format) =>
        formatPattern[format]
          .test(command),
    )

  const formatCandidates =
    requestedFormat
      ? candidates.filter(
          ({ artifact }) =>
            artifact.format ===
              requestedFormat,
        )
      : candidates

  if (formatCandidates.length === 0) {
    return null
  }

  if (
    /\b(?:first|oldest|pehla|pehli)\b/i
      .test(command)
  ) {
    return formatCandidates[0]
  }

  return formatCandidates[
    formatCandidates.length - 1
  ]
}
