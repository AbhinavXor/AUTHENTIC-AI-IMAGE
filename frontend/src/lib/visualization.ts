export type ChartPrimitive =
  | string
  | number
  | boolean
  | null

export interface ChartTable {
  columns: string[]
  rows: ChartPrimitive[][]
}

export interface ChartSpec {
  version: '1.0'
  title: string
  description?: string
  altText?: string
  source?: string
  updatedAt?: string
  estimated: boolean
  limitations: string[]
  option: Record<string, unknown>
  table?: ChartTable
}

export interface ParsedChartResponse {
  markdown: string
  charts: ChartSpec[]
  rejectedCount: number
}

const chartPattern =
  /```authentic-chart\s*([\s\S]*?)```/gi

const allowedSeriesTypes =
  new Set([
    'line',
    'bar',
    'pie',
    'scatter',
    'effectScatter',
    'radar',
    'tree',
    'treemap',
    'sunburst',
    'boxplot',
    'candlestick',
    'heatmap',
    'parallel',
    'lines',
    'graph',
    'sankey',
    'funnel',
    'gauge',
    'pictorialBar',
    'themeRiver',
  ])

const blockedOptionKeys =
  new Set([
    'graphic',
    'renderItem',
    'toolbox',
  ])

const maximumCharts = 4
const maximumBlockLength = 200_000
const maximumRows = 1_000
const maximumColumns = 30

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === 'object' &&
    value !== null &&
    !Array.isArray(value)
  )
}

function cleanText(
  value: unknown,
  maximumLength: number,
): string | undefined {
  if (typeof value !== 'string') {
    return undefined
  }

  const cleaned = value.trim()

  return cleaned
    ? cleaned.slice(0, maximumLength)
    : undefined
}

function sanitizeJson(
  value: unknown,
): unknown {
  if (
    value === null ||
    typeof value === 'boolean' ||
    typeof value === 'string'
  ) {
    if (
      typeof value === 'string' &&
      /(?:javascript:|data:text\/html|https?:\/\/)/i.test(
        value,
      )
    ) {
      throw new Error(
        'External resources are not allowed in chart options.',
      )
    }

    return value
  }

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new Error(
        'Chart numbers must be finite.',
      )
    }

    return value
  }

  if (Array.isArray(value)) {
    return value.map(sanitizeJson)
  }

  if (!isRecord(value)) {
    throw new Error(
      'Unsupported chart option value.',
    )
  }

  const result: Record<string, unknown> = {}

  for (const [key, item] of Object.entries(value)) {
    if (blockedOptionKeys.has(key)) {
      continue
    }

    result[key] = sanitizeJson(item)
  }

  return result
}

function validateSeries(
  option: Record<string, unknown>,
): void {
  const rawSeries = option.series

  if (rawSeries === undefined) {
    throw new Error(
      'Chart requires at least one series.',
    )
  }

  const seriesList = Array.isArray(rawSeries)
    ? rawSeries
    : [rawSeries]

  if (!seriesList.length) {
    throw new Error(
      'Chart series cannot be empty.',
    )
  }

  for (const series of seriesList) {
    if (
      !isRecord(series) ||
      typeof series.type !== 'string' ||
      !allowedSeriesTypes.has(series.type)
    ) {
      throw new Error(
        'Chart contains an unsupported series type.',
      )
    }
  }
}

function normalizeTable(
  value: unknown,
): ChartTable | undefined {
  if (
    !isRecord(value) ||
    !Array.isArray(value.columns) ||
    !Array.isArray(value.rows)
  ) {
    return undefined
  }

  const columns = value.columns
    .filter(
      (column): column is string =>
        typeof column === 'string',
    )
    .slice(0, maximumColumns)
    .map((column) =>
      column.trim().slice(0, 80),
    )
    .filter(Boolean)

  if (!columns.length) {
    return undefined
  }

  const rows: ChartPrimitive[][] = []

  for (const rawRow of value.rows.slice(0, maximumRows)) {
    if (!Array.isArray(rawRow)) {
      continue
    }

    rows.push(
      rawRow
        .slice(0, columns.length)
        .map((cell): ChartPrimitive => {
          if (
            cell === null ||
            typeof cell === 'string' ||
            typeof cell === 'number' ||
            typeof cell === 'boolean'
          ) {
            return cell
          }

          return (
            JSON.stringify(cell) ??
            String(cell)
          )
        }),
    )
  }

  return {
    columns,
    rows,
  }
}

function normalizeChart(
  value: unknown,
): ChartSpec {
  if (!isRecord(value)) {
    throw new Error(
      'Chart specification must be an object.',
    )
  }

  const title = cleanText(
    value.title,
    140,
  )

  if (!title || !isRecord(value.option)) {
    throw new Error(
      'Chart title and option are required.',
    )
  }

  const sanitizedOption =
    sanitizeJson(value.option)

  if (!isRecord(sanitizedOption)) {
    throw new Error(
      'Invalid chart option.',
    )
  }

  validateSeries(sanitizedOption)

  return {
    version: '1.0',
    title,
    description: cleanText(
      value.description,
      500,
    ),
    altText: cleanText(
      value.alt_text ?? value.altText,
      700,
    ),
    source: cleanText(
      value.source,
      300,
    ),
    updatedAt: cleanText(
      value.timestamp ?? value.updatedAt,
      100,
    ),
    estimated:
      value.estimated === true,
    limitations:
      Array.isArray(value.limitations)
        ? value.limitations
            .filter(
              (item): item is string =>
                typeof item === 'string',
            )
            .slice(0, 8)
            .map((item) =>
              item.trim().slice(0, 240),
            )
            .filter(Boolean)
        : [],
    option: sanitizedOption,
    table: normalizeTable(
      value.table,
    ),
  }
}

export function parseChartResponse(
  content: string,
): ParsedChartResponse {
  const charts: ChartSpec[] = []
  let rejectedCount = 0

  const markdown = content.replace(
    chartPattern,
    (
      _complete,
      rawJson: string,
    ) => {
      if (
        charts.length >= maximumCharts ||
        rawJson.length > maximumBlockLength
      ) {
        rejectedCount += 1
        return ''
      }

      try {
        charts.push(
          normalizeChart(
            JSON.parse(rawJson),
          ),
        )
      } catch {
        rejectedCount += 1
      }

      return ''
    },
  )

  return {
    markdown: markdown
      .replace(/\n{3,}/g, '\n\n')
      .trim(),
    charts,
    rejectedCount,
  }
}
