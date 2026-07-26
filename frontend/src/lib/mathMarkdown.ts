const inlineParenthesisPattern =
  /\\\(([\s\S]*?)\\\)/g

const displayBracketPattern =
  /\\\[([\s\S]*?)\\\]/g

/*
 * Repair the common provider typo `$$x$`
 * without changing valid `$$...$$`
 * display equations.
 */
const unbalancedInlinePattern =
  /\$\$([^$\n]{1,220})\$(?!\$)/g

const protectedSegmentPattern =
  /(```[\s\S]*?```|`[^`\n]*`|\$\$[\s\S]*?\$\$|\$[^$\n]*\$)/g

const standaloneFunctionPattern =
  /^(\s*)((?:[fgh](?:')?\s*\(\s*x\s*\))\s*=\s*[^\n]{1,180})(\s*)$/gim

const rawFunctionExpressionPattern =
  /\b((?:[fgh](?:')?\s*\(\s*x\s*\))\s*=\s*.*?)(?=\s+(?:is|has|where|for|with|within|on|over|and|which|that|so|therefore|due)\b|[.;,\n]|$)/gi

const rawIntervalPattern =
  /([-+]?\d+(?:\.\d+)?\s*(?:<=|≤)\s*[xyz]\s*(?:<=|≤)\s*[-+]?\d+(?:\.\d+)?)/g

const rawAssignmentPattern =
  /\b([xyz]\s*=\s*[+\-±]?\s*(?:√\s*)?(?:\d+(?:\.\d+)?|[a-z])(?:\s*\/\s*\d+(?:\.\d+)?)?)/gi

const rawPowerPattern =
  /\b([a-z]\s*\^\s*\{?[-+]?\d+\}?)/gi

const rawFunctionTokenPattern =
  /\b([fgh](?:')?\s*\(\s*x\s*\))/gi

const rawRootPattern =
  /([+\-±]?\s*√\s*(?:\([^)\n]+\)|[a-z0-9.]+))/gi


const inlineMathSegmentPattern =
  /(^|[^$])\$([^$\n]+)\$(?!\$)/g

const displayMathPromotionMarker =
  'AUTHENTIC_COMPLEX_MATH_DISPLAY_V1'

function toLatex(
  expression: string,
): string {
  return expression
    .replace(/≤/g, '\\le ')
    .replace(/≥/g, '\\ge ')
    .replace(/<=/g, '\\le ')
    .replace(/>=/g, '\\ge ')
    .replace(/±/g, '\\pm ')
    .replace(/×/g, '\\times ')
    .replace(/÷/g, '\\div ')
    .replace(
      /√\s*\(([^)\n]+)\)/g,
      '\\sqrt{$1}',
    )
    .replace(
      /√\s*([a-z0-9.]+)/gi,
      '\\sqrt{$1}',
    )
    .replace(
      /([a-z])\s*\^\s*\{?([-+]?\d+)\}?/gi,
      '$1^{$2}',
    )
    .replace(/\s+/g, ' ')
    .trim()
}

function inlineMath(
  expression: string,
): string {
  return `$${toLatex(expression)}$`
}

function normalizeUnprotectedText(
  content: string,
): string {
  let normalized =
    content.replace(
      standaloneFunctionPattern,
      (
        _complete,
        leading: string,
        expression: string,
        trailing: string,
      ) =>
        `${leading}\n\n$$\n${toLatex(expression)}\n$$\n\n${trailing}`,
    )

  normalized =
    normalized.replace(
      rawFunctionExpressionPattern,
      (
        _complete,
        expression: string,
      ) =>
        inlineMath(expression),
    )

  return normalized
    .split(
      /(\$\$[\s\S]*?\$\$|\$[^$\n]*\$)/g,
    )
    .map((segment) => {
      if (
        segment.startsWith('$')
      ) {
        return segment
      }

      return segment
        .replace(
          rawIntervalPattern,
          (
            _complete,
            expression: string,
          ) =>
            inlineMath(expression),
        )
        .replace(
          rawAssignmentPattern,
          (
            _complete,
            expression: string,
          ) =>
            inlineMath(expression),
        )
        .replace(
          rawRootPattern,
          (
            _complete,
            expression: string,
          ) =>
            inlineMath(expression),
        )
        .replace(
          rawPowerPattern,
          (
            _complete,
            expression: string,
          ) =>
            inlineMath(expression),
        )
        .replace(
          rawFunctionTokenPattern,
          (
            _complete,
            expression: string,
          ) =>
            inlineMath(expression),
        )
    })
    .join('')
}

function normalizeRawMath(
  content: string,
): string {
  return content
    .split(
      protectedSegmentPattern,
    )
    .map((segment) => {
      if (
        segment.startsWith('```') ||
        segment.startsWith('`') ||
        segment.startsWith('$')
      ) {
        return segment
      }

      return normalizeUnprotectedText(
        segment,
      )
    })
    .join('')
}


function shouldPromoteInlineMath(
  expression: string,
): boolean {
  const normalized =
    expression.trim()

  const fractionCount =
    (
      normalized.match(
        /\\(?:d|t)?frac\s*\{/g,
      ) ?? []
    ).length

  const relationCount =
    (
      normalized.match(
        /(?:=|\\le|\\ge|<|>)/g,
      ) ?? []
    ).length

  const hasNonTrivialFraction =
    fractionCount > 0 &&
    (
      normalized.length >= 30 ||
      /\\frac\{[^{}]*[+\-][^{}]*\}\{/.test(
        normalized,
      ) ||
      /\\frac\{[^{}]{9,}\}/.test(
        normalized,
      ) ||
      /\}\{[^{}]*[+\-][^{}]*\}/.test(
        normalized,
      )
    )

  const hasLongDerivative =
    (
      /(?:[fgh](?:')?\s*\([^)]*\)|\\frac\{d)/.test(
        normalized,
      ) &&
      normalized.length >= 34
    )

  const hasLargeOperator =
    /\\(?:int|sum|prod|lim)\b/.test(
      normalized,
    ) &&
    normalized.length >= 36

  return (
    normalized.includes(
      '\\begin{',
    ) ||
    normalized.length >= 72 ||
    hasNonTrivialFraction ||
    hasLongDerivative ||
    hasLargeOperator ||
    (
      relationCount >= 2 &&
      normalized.length >= 36
    )
  )
}

function promoteComplexInlineMath(
  content: string,
): string {
  const promoted =
    content.replace(
      inlineMathSegmentPattern,
      (
        complete,
        prefix: string,
        expression: string,
      ) => {
        if (
          !shouldPromoteInlineMath(
            expression,
          )
        ) {
          return complete
        }

        return (
          `${prefix}\n\n$$\n` +
          `${expression.trim()}\n` +
          '$$\n\n'
        )
      },
    )

  return promoted.replace(
    /\n{3,}/g,
    '\n\n',
  )
}

export function normalizeMathMarkdown(
  content: string,
): string {
  if (!content) {
    return content
  }

  const normalizedDelimiters =
    content
      .replace(
        displayBracketPattern,
        (
          _complete,
          expression: string,
        ) =>
          `\n\n$$\n${expression.trim()}\n$$\n\n`,
      )
      .replace(
        inlineParenthesisPattern,
        (
          _complete,
          expression: string,
        ) =>
          `$${expression.trim()}$`,
      )
      .replace(
        unbalancedInlinePattern,
        (
          _complete,
          expression: string,
        ) =>
          `$${expression.trim()}$`,
      )

  const normalizedMath =
    normalizeRawMath(
      normalizedDelimiters,
    )

  return promoteComplexInlineMath(
    normalizedMath,
  )
}
