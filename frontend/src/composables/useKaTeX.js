import { ref } from 'vue'
import katex from 'katex'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// Configure marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

// Shared reactive raw mode toggle
export const isRawMode = ref(localStorage.getItem('rawMode') === 'true')
if (typeof window !== 'undefined') window.__rawMode = isRawMode.value

// ── Helpers ─────────────────────────────────────

/**
 * Decode common HTML entities that LLMs sometimes output instead of literal chars.
 * Essential for KaTeX compatibility: &gt; → >, &lt; → <, &amp; → &
 */
function decodeHTMLEntities(text) {
  return text
    .replace(/&gt;/g, '>')
    .replace(/&lt;/g, '<')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
}

// ── LaTeX rendering ──────────────────────────────

/**
 * Render LaTeX formulas in a plain text or HTML string.
 * Handles $$...$$ (display) and $...$ (inline).
 * Safe to call on already-rendered HTML.
 */
export function renderLatex(text) {
  if (!text) return ''

  // Collect placeholders to avoid double-processing
  const protected_ = []

  // Step 1: protect existing KaTeX HTML and code blocks
  let result = text
    .replace(/<span class="katex"[^>]*>[\s\S]*?<\/span>/g, (m) => {
      protected_.push(m); return `KATEX${protected_.length - 1}`
    })
    .replace(/<code[^>]*>[\s\S]*?<\/code>/g, (m) => {
      protected_.push(m); return `CODE${protected_.length - 1}`
    })
    .replace(/<pre[^>]*>[\s\S]*?<\/pre>/g, (m) => {
      protected_.push(m); return `PRE${protected_.length - 1}`
    })

  // Step 2: render display math $$...$$ and \[...\]
  result = result.replace(/\$\$([\s\S]*?)\$\$/g, (_, formula) => {
    try {
      const cleaned = decodeHTMLEntities(formula.trim())
      return katex.renderToString(cleaned, { displayMode: true, throwOnError: false })
    } catch {
      return `<span class="katex-error">$${formula}$</span>`
    }
  })
  result = result.replace(/\\\[([\s\S]*?)\\\]/g, (_, formula) => {
    try {
      const cleaned = decodeHTMLEntities(formula.trim())
      return katex.renderToString(cleaned, { displayMode: true, throwOnError: false })
    } catch {
      return `<span class="katex-error">\\[${formula}\\]</span>`
    }
  })

  // Step 3: render inline math $...$ (but not $$)
  result = result.replace(/\$([^$]+?)\$/g, (_, formula) => {
    try {
      const cleaned = decodeHTMLEntities(formula.trim())
      return katex.renderToString(cleaned, { displayMode: false, throwOnError: false })
    } catch {
      return `<span class="katex-error">$${formula}$</span>`
    }
  })

  // Step 4: restore protected blocks
  result = result.replace(/KATEX(\d+)/g, (_, i) => protected_[+i])
  result = result.replace(/CODE(\d+)/g, (_, i) => protected_[+i])
  result = result.replace(/PRE(\d+)/g, (_, i) => protected_[+i])

  return result
}

// ── Markdown rendering ───────────────────────────

/**
 * Render Markdown text to HTML, with LaTeX protection.
 *
 * The pipeline: protect LaTeX → Markdown → HTML → restore LaTeX → KaTeX.
 * This prevents markdown parsers from mangling LaTeX delimiters
 * (e.g., underscores in $x_1$ being treated as italics).
 */
export function renderMarkdown(text) {
  if (!text) return ''

  // Raw/source mode: show unrendered text for easy copying
  if (isRawMode.value) {
    return `<pre style="white-space:pre-wrap;font-family:monospace;font-size:14px;line-height:1.6;margin:0">${text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</pre>`
  }

  // Step 1: protect LaTeX before Markdown parsing
  const latexBlocks = []
  let protected_ = text

  // Protect display math: $$...$$ and \[...\]
  protected_ = protected_.replace(/\$\$([\s\S]*?)\$\$/g, (match) => {
    latexBlocks.push(match)
    return `LATEX${latexBlocks.length - 1}`
  })
  protected_ = protected_.replace(/\\\[([\s\S]*?)\\\]/g, (match) => {
    latexBlocks.push(match)
    return `LATEX${latexBlocks.length - 1}`
  })

  // Then protect inline math
  protected_ = protected_.replace(/\$([^$]+?)\$/g, (match, inner) => {
    // Skip if it looks like a dollar amount ($100, $1.50)
    if (/^\d+(\.\d+)?$/.test(inner.trim())) return match
    latexBlocks.push(match)
    return `LATEX${latexBlocks.length - 1}`
  })

  // Step 1.5: protect literal underscore runs (fill-in-blank: _____)
  // Must run BEFORE Step 1.5b and marked.parse() to prevent _ being parsed as italic/bold
  const underscoreBlocks = []
  protected_ = protected_.replace(/_{3,}/g, (match) => {
    underscoreBlocks.push(match)
    return `USCORE${underscoreBlocks.length - 1}`
  })

  // Step 1.5b: normalize common AI markdown formatting quirks
  // LaTeX is already protected → safe to do aggressive regex here
  // Fix ** text ** → **text** (spaces inside bold markers)
  protected_ = protected_.replace(/\*\*[ \t]*([^*\n]+?)[ \t]*\*\*/g, (_, c) => `**${c.trim()}**`)
  // Fix __ text __ → __text__ (alternative bold syntax)
  protected_ = protected_.replace(/__[ \t]*([^_\n]+?)[ \t]*__/g, (_, c) => `__${c.trim()}__`)
  // Fix * text * → *text* (italic, require ≥2 chars to skip "* *" false positives)
  protected_ = protected_.replace(/\*[ \t]+([^*\n]{2,}?)[ \t]+\*/g, (_, c) => `*${c.trim()}*`)

  // Step 2: Markdown → HTML
  let html = marked.parse(protected_)

  // Step 2.5: restore underscore placeholders (before LaTeX restore)
  html = html.replace(/USCORE(\d+)/g, (_, i) => underscoreBlocks[+i])

  // Step 3: restore LaTeX placeholders
  html = html.replace(/LATEX(\d+)/g, (_, i) => latexBlocks[+i])

  // Step 4: sanitize HTML (XSS protection)
  html = DOMPurify.sanitize(html)

  // Step 5: render LaTeX → KaTeX HTML
  html = renderLatex(html)

  return html
}
