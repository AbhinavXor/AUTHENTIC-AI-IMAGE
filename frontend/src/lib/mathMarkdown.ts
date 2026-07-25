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
  /\$\$([^$\n]{1,160})\$(?!\$)/g

export function normalizeMathMarkdown(
  content: string,
): string {
  if (!content) {
    return content
  }

  return content
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
}
