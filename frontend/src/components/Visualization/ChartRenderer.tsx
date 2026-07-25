import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import {
  BarChart,
  BoxplotChart,
  CandlestickChart,
  EffectScatterChart,
  FunnelChart,
  GaugeChart,
  GraphChart,
  HeatmapChart,
  LineChart,
  LinesChart,
  ParallelChart,
  PictorialBarChart,
  PieChart,
  RadarChart,
  SankeyChart,
  ScatterChart,
  SunburstChart,
  ThemeRiverChart,
  TreeChart,
  TreemapChart,
} from 'echarts/charts'
import {
  AriaComponent,
  AxisPointerComponent,
  DataZoomComponent,
  DatasetComponent,
  GeoComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  MarkPointComponent,
  ParallelComponent,
  PolarComponent,
  RadarComponent,
  SingleAxisComponent,
  TitleComponent,
  TooltipComponent,
  TransformComponent,
  VisualMapComponent,
} from 'echarts/components'
import {
  LabelLayout,
  UniversalTransition,
} from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import {
  Download,
  Maximize2,
  Minimize2,
  Table2,
} from 'lucide-react'
import type {
  ChartSpec,
  ChartPrimitive,
} from '../../lib/visualization'

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  ScatterChart,
  EffectScatterChart,
  RadarChart,
  TreeChart,
  TreemapChart,
  SunburstChart,
  BoxplotChart,
  CandlestickChart,
  HeatmapChart,
  ParallelChart,
  LinesChart,
  GraphChart,
  SankeyChart,
  FunnelChart,
  GaugeChart,
  PictorialBarChart,
  ThemeRiverChart,
  GridComponent,
  PolarComponent,
  RadarComponent,
  ParallelComponent,
  SingleAxisComponent,
  GeoComponent,
  TooltipComponent,
  AxisPointerComponent,
  TitleComponent,
  LegendComponent,
  DatasetComponent,
  TransformComponent,
  VisualMapComponent,
  DataZoomComponent,
  MarkPointComponent,
  MarkLineComponent,
  MarkAreaComponent,
  AriaComponent,
  LabelLayout,
  UniversalTransition,
  CanvasRenderer,
])

interface ChartRendererProps {
  spec: ChartSpec
}

function useDarkMode(): boolean {
  const getValue = () =>
    window.matchMedia(
      '(prefers-color-scheme: dark)',
    ).matches

  const [isDark, setIsDark] =
    useState(getValue)

  useEffect(() => {
    const query = window.matchMedia(
      '(prefers-color-scheme: dark)',
    )

    const update = () =>
      setIsDark(query.matches)

    query.addEventListener(
      'change',
      update,
    )

    return () => {
      query.removeEventListener(
        'change',
        update,
      )
    }
  }, [])

  return isDark
}

function formatCell(
  value: ChartPrimitive,
): string {
  if (value === null) {
    return '—'
  }

  if (typeof value === 'number') {
    return new Intl.NumberFormat(
      undefined,
      {
        maximumFractionDigits: 4,
      },
    ).format(value)
  }

  return String(value)
}

function createFilename(
  title: string,
): string {
  const normalized = title
    .toLowerCase()
    .replace(
      /[^a-z0-9]+/g,
      '-',
    )
    .replace(
     /^-+|-+$/g,
      '',
    )
    .slice(0, 72)

  return normalized || 'authentic-chart'
}

function buildOption(
  spec: ChartSpec,
  isDark: boolean,
): EChartsOption {
  const source =
    spec.option as EChartsOption

  const palette = isDark
    ? [
        '#71c4a9',
        '#86a8ff',
        '#efb467',
        '#d88ade',
        '#ef7e7e',
        '#70c6df',
        '#b3cc78',
        '#c7a2ff',
      ]
    : [
        '#138f74',
        '#4c76df',
        '#dc9136',
        '#ac58b9',
        '#cf5353',
        '#2796b0',
        '#7f9737',
        '#8056c9',
      ]

  return {
    ...source,
    color: palette,
    backgroundColor: 'transparent',
    animationDuration: 420,
    animationDurationUpdate: 260,
    textStyle: {
      color: isDark
        ? '#eef3f0'
        : '#1a211d',
      fontFamily:
        'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    },
    aria: {
      enabled: true,
      description:
        spec.altText ??
        spec.description ??
        spec.title,
    },
  }
}

export default function ChartRenderer({
  spec,
}: ChartRendererProps) {
  const chartRef =
    useRef<ReactEChartsCore | null>(null)

  const [showTable, setShowTable] =
    useState(false)

  const [isExpanded, setIsExpanded] =
    useState(false)

  const isDark = useDarkMode()

  const option = useMemo(
    () =>
      buildOption(
        spec,
        isDark,
      ),
    [
      spec,
      isDark,
    ],
  )

  const downloadPng = () => {
    const instance =
      chartRef.current
        ?.getEchartsInstance()

    if (!instance) {
      return
    }

    const dataUrl =
      instance.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor:
          isDark
            ? '#0d100f'
            : '#ffffff',
      })

    const link =
      document.createElement('a')

    link.href = dataUrl
    link.download =
      `${createFilename(
        spec.title,
      )}.png`

    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  return (
    <section
      aria-label={
        spec.altText ??
        spec.title
      }
      className={`authentic-chart-card ${
        isExpanded
          ? 'is-expanded'
          : ''
      }`}
    >
      <header className="authentic-chart-header">
        <div className="authentic-chart-heading">
          <strong>
            {spec.title}
          </strong>

          {spec.description && (
            <p>
              {spec.description}
            </p>
          )}
        </div>

        <div className="authentic-chart-actions">
          {spec.table && (
            <button
              aria-label={
                showTable
                  ? 'Hide chart data'
                  : 'Show chart data'
              }
              aria-pressed={showTable}
              onClick={() =>
                setShowTable(
                  (current) =>
                    !current,
                )
              }
              title={
                showTable
                  ? 'Hide data'
                  : 'Show data'
              }
              type="button"
            >
              <Table2
                size={17}
                strokeWidth={1.8}
              />
            </button>
          )}

          <button
            aria-label="Download chart as PNG"
            onClick={downloadPng}
            title="Download PNG"
            type="button"
          >
            <Download
              size={17}
              strokeWidth={1.8}
            />
          </button>

          <button
            aria-label={
              isExpanded
                ? 'Close expanded chart'
                : 'Expand chart'
            }
            aria-pressed={isExpanded}
            onClick={() =>
              setIsExpanded(
                (current) =>
                  !current,
              )
            }
            title={
              isExpanded
                ? 'Close expanded view'
                : 'Expand'
            }
            type="button"
          >
            {isExpanded ? (
              <Minimize2
                size={17}
                strokeWidth={1.8}
              />
            ) : (
              <Maximize2
                size={17}
                strokeWidth={1.8}
              />
            )}
          </button>
        </div>
      </header>

      <div className="authentic-chart-canvas">
        <ReactEChartsCore
          echarts={echarts}
          lazyUpdate
          notMerge
          option={option}
          opts={{
            renderer: 'canvas',
          }}
          ref={chartRef}
          style={{
            width: '100%',
            height: '100%',
          }}
        />
      </div>

      {showTable && spec.table && (
        <div className="authentic-chart-table-wrapper">
          <table className="authentic-chart-table">
            <thead>
              <tr>
                {spec.table.columns.map(
                  (
                    column,
                    index,
                  ) => (
                    <th
                      key={`${column}:${index}`}
                      scope="col"
                    >
                      {column}
                    </th>
                  ),
                )}
              </tr>
            </thead>

            <tbody>
              {spec.table.rows.map(
                (
                  row,
                  rowIndex,
                ) => (
                  <tr key={rowIndex}>
                    {spec.table?.columns.map(
                      (
                        _column,
                        columnIndex,
                      ) => (
                        <td
                          key={columnIndex}
                        >
                          {formatCell(
                            row[
                              columnIndex
                            ] ?? null,
                          )}
                        </td>
                      ),
                    )}
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}

      <footer className="authentic-chart-footer">
        <div>
          {spec.estimated && (
            <span className="authentic-chart-estimate">
              Estimate
            </span>
          )}

          {spec.source && (
            <span>
              Source: {spec.source}
            </span>
          )}

          {spec.updatedAt && (
            <span>
              Updated: {spec.updatedAt}
            </span>
          )}
        </div>

        {spec.limitations.length >
          0 && (
          <details>
            <summary>
              Limitations
            </summary>

            <ul>
              {spec.limitations.map(
                (
                  limitation,
                  index,
                ) => (
                  <li key={index}>
                    {limitation}
                  </li>
                ),
              )}
            </ul>
          </details>
        )}
      </footer>
    </section>
  )
}
