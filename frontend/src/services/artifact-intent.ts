import type {
  ArtifactIntentContext,
  ArtifactIntentDecision,
} from '../types/artifact-intent'


const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ??
  'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '')


function isDecision(
  value: unknown,
): value is ArtifactIntentDecision {
  if (
    !value ||
    typeof value !== 'object'
  ) {
    return false
  }

  const candidate = value as Partial<
    ArtifactIntentDecision
  >

  return (
    (
      candidate.action === 'create' ||
      candidate.action === 'revise' ||
      candidate.action === 'none'
    ) &&
    (
      candidate.format === null ||
      candidate.format === 'pdf' ||
      candidate.format === 'docx' ||
      candidate.format === 'pptx' ||
      candidate.format === 'zip'
    ) &&
    typeof candidate.confidence === 'number' &&
    typeof candidate.reason === 'string'
  )
}


export async function resolveDynamicArtifactIntent(
  message: string,
  context: ArtifactIntentContext,
): Promise<ArtifactIntentDecision | null> {
  const normalized = message.trim()
  if (!normalized) {
    return null
  }

  const classifierMessage =
    normalized.length <= 12_000
      ? normalized
      : (
          normalized.slice(0, 5_900)
          + '\n\n[...middle source omitted for intent classification...]\n\n'
          + normalized.slice(-5_900)
        )

  const controller = new AbortController()
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    8_000,
  )

  try {
    const response = await fetch(
      `${apiBaseUrl}/artifacts/intent`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: classifierMessage,
          has_attachment:
            context.hasAttachment,
          attachment_names:
            context.attachmentNames,
          has_generated_artifact:
            context.hasGeneratedArtifact,
        }),
        signal: controller.signal,
      },
    )

    if (!response.ok) {
      return null
    }

    const payload = await response.json() as unknown
    return isDecision(payload)
      ? payload
      : null
  } catch {
    // Classification is an enhancement. A provider/network failure must
    // never prevent the user's normal chat request from continuing.
    return null
  } finally {
    window.clearTimeout(timeoutId)
  }
}
