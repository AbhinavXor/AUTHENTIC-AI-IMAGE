export type ArtifactPromptMode =
  | 'auto'
  | 'standard'
  | 'compact'


const highValueInstruction =
  /\b(?:redesign|preserve|retain|remove|omit|without|include|title|filename|unbranded|watermark|equation|formula|math|chart|graph|table|diagram|architecture|reference|appendix|landscape|page\s+number|header|footer|author|date|language|audience|b\.?tech|project|research|professional|professionally|premium|polished|publication[- ]quality|submission[- ]ready|faculty[- ]ready|final[- ]ready|best\s+design)\b/i


export type ArtifactPresentationTier =
  | 'standard'
  | 'professional'
  | 'premium'


export function detectArtifactPresentationTier(
  prompt: string,
): ArtifactPresentationTier {
  if (/\b(?:best\s+professional|highly\s+professional|most\s+professional|premium|publication[- ]quality|submission[- ]ready|faculty[- ]ready|final[- ]ready|portfolio[- ]ready|executive[- ]grade|world[- ]class|polished|professionally\s+(?:final|redesign|design|ready))\b/i.test(prompt)) {
    return 'premium'
  }
  if (/\b(?:professional|professionally|academic[- ]quality|college\s+submission)\b/i.test(prompt)) {
    return 'professional'
  }
  return 'standard'
}


export function selectArtifactProfile(
  prompt: string,
  sourceKind?: string,
): string {
  const normalized = prompt.toLocaleLowerCase()
  if (
    sourceKind === 'uploaded_file'
    && /\b(?:redesign|rebuild|restyle|reformat|new\s+design|change\s+(?:the\s+)?layout|(?:create|make|generate|prepare|produce|bana\s*do|banao)\b[\s\S]{0,120}\b(?:professional|polished|final[- ]ready|best\s+design)?[\s\S]{0,80}\b(?:pdf|document|file)\b|\b(?:professional|polished|final[- ]ready|best\s+design)\b[\s\S]{0,100}\b(?:pdf|document|file)\b)\b/i
      .test(normalized)
  ) {
    return 'redesign_existing'
  }
  if (/\b(?:b\.?tech|final[-\s]?year|capstone|mini\s+project|major\s+project|lab\s+report|viva)\b/i.test(normalized)) {
    return 'btech_project_report'
  }
  if (/\b(?:research\s+paper|literature\s+review|methodology|abstract|experiment)\b/i.test(normalized)) {
    return 'research_paper'
  }
  if (/\b(?:equation|formula|calculus|algebra|theorem|proof|study\s+notes?|exam|chapter)\b/i.test(normalized)) {
    return 'academic_learning'
  }
  if (/\b(?:analytics|dataset|statistics?|benchmark|kpi|cost[-\s]?benefit|roi|graph|chart)\b/i.test(normalized)) {
    return 'data_analysis'
  }
  if (/\b(?:api|system\s+architecture|technical\s+spec|implementation|deployment|security)\b/i.test(normalized)) {
    return 'technical_report'
  }
  if (/\b(?:executive|board|leadership|strategy|risk\s+matrix|roadmap)\b/i.test(normalized)) {
    return 'executive_report'
  }
  return 'professional_general'
}


export function compactArtifactInstruction(
  prompt: string,
  hasSeparateSource: boolean,
): string {
  const normalized = prompt
    .replace(/\r/g, '\n')
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (!hasSeparateSource) {
    return prompt.trim()
  }

  const selected: string[] = []
  const seen = new Set<string>()
  for (const line of normalized) {
    const key = line.toLocaleLowerCase()
    if (
      seen.has(key)
      || (
        selected.length > 0
        && !highValueInstruction.test(line)
      )
    ) {
      continue
    }
    seen.add(key)
    selected.push(line)
    if (selected.join(' ').length >= 2_400) {
      break
    }
  }

  const result = selected.join(' ').trim()
  if (!result) {
    return 'Create the requested professional document from the supplied source.'
  }
  if (result.length <= 2_400) {
    return result
  }
  return `${result.slice(0, 2_360).replace(/\s+\S*$/, '')}.`
}


export function artifactPromptMode(
  originalPrompt: string,
  hasSeparateSource: boolean,
): ArtifactPromptMode {
  return (
    hasSeparateSource
    || originalPrompt.length > 4_000
  )
    ? 'compact'
    : 'auto'
}
