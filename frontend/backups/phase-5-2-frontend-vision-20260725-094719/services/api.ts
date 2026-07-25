export type ChatRole = 'user' | 'assistant'

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
  provider: 'groq'
  model: string
  request_id: string | null
  usage: TokenUsage
}

interface ApiErrorPayload {
  detail?: string
}

interface StreamEventPayload {
  content?: string
  model?: string
  detail?: string
}

export interface StreamResult {
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
  } catch {
    // Use the fallback below.
  }

  return 'The request could not be completed.'
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
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
        signal,
      },
    )
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === 'AbortError'
    ) {
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

  return (await response.json()) as ChatResponse
}

function parseSseBlock(
  block: string,
): {
  event: string
  payload: StreamEventPayload
} | null {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
      continue
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart())
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
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(request),
        signal,
      },
    )
  } catch (error) {
    if (
      error instanceof DOMException &&
      error.name === 'AbortError'
    ) {
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

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  let buffer = ''
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

    const blocks = buffer.split(/\r?\n\r?\n/)
    buffer = blocks.pop() ?? ''

    for (const block of blocks) {
      const parsed = parseSseBlock(block)

      if (!parsed) {
        continue
      }

      if (
        parsed.event === 'token' &&
        typeof parsed.payload.content === 'string'
      ) {
        handlers.onToken(
          parsed.payload.content
        )
      }

      if (parsed.event === 'done') {
        model =
          parsed.payload.model ?? ''
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
    model,
  }
}
