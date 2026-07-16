import katex from 'katex'
import { marked } from 'marked'

// Configure marked for safety and LaTeX compatibility
marked.setOptions({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(text) {
  if (!text) return ''
  // Step 1: Markdown → HTML
  let html = marked.parse(text)
  // Step 2: LaTeX → KaTeX
  html = renderLatex(html)
  return html
}

export function renderLatex(text) {
  if (!text) return ''
  // Replace display math $$...$$
  let result = text.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: true, throwOnError: false })
    } catch {
      return `<span class="text-red-500">${formula}</span>`
    }
  })
  // Replace inline math $...$
  result = result.replace(/\$([^$]+?)\$/g, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), { displayMode: false, throwOnError: false })
    } catch {
      return `<span class="text-red-500">${formula}</span>`
    }
  })
  return result
}
