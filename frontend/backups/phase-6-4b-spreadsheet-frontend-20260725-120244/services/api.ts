export type ChatRole =
  | 'user'
  | 'assistant'

export interface ChatMessage {
  role: ChatRole
  content: string
}

export interface ChatRequest {
  message: string
  history: ChatMessage[]
}

export interface TokenUsage {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface ChatResponse {
  answer: string
  provider: string
  model: string
  category?: string
  routing_confidence?: number
  request_id: string | null
  usage: TokenUsage
}

export interface VisionResponse {
  answer: string
  provider: string
  model: string
  filename: string
  mime_type: string
  image_format: string
  width: number
  height: number
  size_bytes: number
  request_id: string | null
  usage: TokenUsage
}


export interface DocumentCitation {
  page: number
  label: string
}

export interface DocumentMetadata {
  title: string | null
  author: string | null
  subject: string | null
  creator: string | null
  producer: string | null
}

export interface DocumentResponse {
  answer: string
  provider: string
  model: string

  filename: string
  mime_type: string
  size_bytes: number

  page_count: number
  extracted_characters: number
  selected_pages: number[]

  analysis_mode:
    | 'text'
    | 'vision_ocr'

  ocr_pages: number[]

  citations: DocumentCitation[]
  metadata: DocumentMetadata

  request_id: string | null
  usage: TokenUsage
}


export type StructuredDocumentType =
  | 'docx'
  | 'text'
  | 'markdown'
  | 'json'
  | 'source_code'

export type StructuredSourceKind =
  | 'section'
  | 'table'
  | 'lines'

export interface StructuredDocumentCitation {
  source_id: string
  label: string
  kind: StructuredSourceKind
}

export interface StructuredDocumentMetadata {
  title: string | null
  author: string | null
  subject: string | null
  keywords: string | null
  created: string | null
  modified: string | null
}

export interface StructuredDocumentResponse {
  answer: string

  provider: string
  model: string

  filename: string
  mime_type: string
  size_bytes: number

  document_type:
    StructuredDocumentType

  extracted_characters: number
  source_count: number
  selected_sources: string[]

  citations:
    StructuredDocumentCitation[]

  metadata:
    StructuredDocumentMetadata

  request_id: string | null
  usage: TokenUsage
}

interface ApiErrorPayload {
  detail?:
    | string
    | Array<{
        msg?: string
      }>
}

interface StreamEventPayload {
  content?: string
  provider?: string
  model?: string
  detail?: string
}

export interface StreamResult {
  provider: string
  model: string
}

interface StreamHandlers {
  onToken: (token: string) => void
}

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ??
  'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(
    message: string,
    status: number,
  ) {
    super(message)

    this.name = 'ApiError'
    this.status = status
  }
}

async function readApiError(
  response: Response,
): Promise<string> {
  try {
    const payload =
      (await response.json()) as ApiErrorPayload

    if (
      typeof payload.detail === 'string' &&
      payload.detail
    ) {
      return payload.detail
    }

    if (
      Array.isArray(payload.detail) &&
      payload.detail.length > 0
    ) {
      const firstMessage =
        payload.detail[0]?.msg

      if (
        typeof firstMessage === 'string' &&
        firstMessage
      ) {
        return firstMessage
      }
    }
  } catch {
    // Use the fallback message below.
  }

  return 'The request could not be completed.'
}

function isAbortError(
  error: unknown,
): boolean {
  return (
    error instanceof DOMException &&
    error.name === 'AbortError'
  )
}

export async function askQuestion(
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<ChatResponse> {
  let response: Response

  try {
    response = await fetch(
      `${apiBaseUrl}/chat`,
      {
        method: 'POST',
        headers: {
          'Content-Type':
            'application/json',
        },
        body: JSON.stringify(request),
        signal,
      },
    )
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ApiError(
      'Authentic AI could not connect to the backend.',
      0,
    )
  }

  if (!response.ok) {
    throw new ApiError(
      await readApiError(response),
      response.status,
    )
  }

  return (
    await response.json()
  ) as ChatResponse
}

export async function analyzeImage(
  file: File,
  prompt: string,
  signal?: AbortSignal,
): Promise<VisionResponse> {
  const formData =
    new FormData()

  formData.append(
    'file',
    file,
    file.name,
  )

  formData.append(
    'prompt',
    prompt,
  )

  let response: Response

  try {
    response = await fetch(
      `${apiBaseUrl}/vision/analyze`,
      {
        method: 'POST',
        body: formData,
        signal,
      },
    )
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ApiError(
      'Authentic AI could not connect to the image-analysis service.',
      0,
    )
  }

  if (!response.ok) {
    throw new ApiError(
      await readApiError(response),
      response.status,
    )
  }

  return (
    await response.json()
  ) as VisionResponse
}


export async function analyzeDocument(
  file: File,
  prompt: string,
  signal?: AbortSignal,
): Promise<DocumentResponse> {
  const formData =
    new FormData()

  formData.append(
    'file',
    file,
    file.name,
  )

  formData.append(
    'prompt',
    prompt,
  )

  let response: Response

  try {
    response = await fetch(
      `${apiBaseUrl}/documents/analyze`,
      {
        method: 'POST',
        body: formData,
        signal,
      },
    )
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ApiError(
      'Authentic AI could not connect to the document-analysis service.',
      0,
    )
  }

  if (!response.ok) {
    throw new ApiError(
      await readApiError(response),
      response.status,
    )
  }

  return (
    await response.json()
  ) as DocumentResponse
}


export async function analyzeStructuredDocument(
  file: File,
  prompt: string,
  signal?: AbortSignal,
): Promise<StructuredDocumentResponse> {
  const formData =
    new FormData()

  formData.append(
    'file',
    file,
    file.name,
  )

  formData.append(
    'prompt',
    prompt,
  )

  let response: Response

  try {
    response = await fetch(
      `${apiBaseUrl}/documents/analyze-file`,
      {
        method: 'POST',
        body: formData,
        signal,
      },
    )
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ApiError(
      'Authentic AI could not connect to the structured-document service.',
      0,
    )
  }

  if (!response.ok) {
    throw new ApiError(
      await readApiError(response),
      response.status,
    )
  }

  return (
    await response.json()
  ) as StructuredDocumentResponse
}

function parseSseBlock(
  block: string,
): {
  event: string
  payload: StreamEventPayload
} | null {
  let event = 'message'
  const dataLines: string[] = []

  for (
    const line
    of block.split(/\r?\n/)
  ) {
    if (line.startsWith('event:')) {
      event = line
        .slice(6)
        .trim()

      continue
    }

    if (line.startsWith('data:')) {
      dataLines.push(
        line
          .slice(5)
          .trimStart(),
      )
    }
  }

  if (dataLines.length === 0) {
    return null
  }

  try {
    return {
      event,
      payload: JSON.parse(
        dataLines.join('\n'),
      ) as StreamEventPayload,
    }
  } catch {
    throw new ApiError(
      'The backend returned an invalid stream event.',
      502,
    )
  }
}

export async function streamQuestion(
  request: ChatRequest,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<StreamResult> {
  let response: Response

  try {
    response = await fetch(
      `${apiBaseUrl}/chat/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type':
            'application/json',
          Accept:
            'text/event-stream',
        },
        body: JSON.stringify(request),
        signal,
      },
    )
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ApiError(
      'Authentic AI could not connect to the backend.',
      0,
    )
  }

  if (!response.ok) {
    throw new ApiError(
      await readApiError(response),
      response.status,
    )
  }

  if (!response.body) {
    throw new ApiError(
      'Streaming is not supported by this browser response.',
      502,
    )
  }

  const reader =
    response.body.getReader()

  const decoder =
    new TextDecoder()

  let buffer = ''
  let provider = ''
  let model = ''

  while (true) {
    const {
      value,
      done,
    } = await reader.read()

    if (done) {
      buffer += decoder.decode()
    } else {
      buffer += decoder.decode(
        value,
        {
          stream: true,
        },
      )
    }

    const blocks =
      buffer.split(
        /\r?\n\r?\n/,
      )

    buffer =
      blocks.pop() ?? ''

    for (const block of blocks) {
      const parsed =
        parseSseBlock(block)

      if (!parsed) {
        continue
      }

      if (
        parsed.event === 'token' &&
        typeof parsed.payload.content ===
          'string'
      ) {
        handlers.onToken(
          parsed.payload.content,
        )
      }

      if (parsed.event === 'done') {
        provider =
          parsed.payload.provider ??
          ''

        model =
          parsed.payload.model ??
          ''
      }

      if (parsed.event === 'error') {
        throw new ApiError(
          parsed.payload.detail ??
            'The AI response could not be completed.',
          502,
        )
      }
    }

    if (done) {
      break
    }
  }

  return {
    provider,
    model,
  }
}
