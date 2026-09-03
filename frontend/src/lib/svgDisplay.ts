export type SvgNaturalSize = {
  width: number
  height: number
}

/** PlantUML/Kroki sometimes emit `data:img/png` — invalid in Chrome for inline SVG/images. */
export function normalizeSvgDataUris(svgMarkup: string): string {
  return svgMarkup.replace(/data:img\/png/gi, 'data:image/png')
}

/** Strip root width/height attrs that fight CSS; keep viewBox for aspect ratio. */
export function prepareSvgForDisplay(svgMarkup: string): string {
  const normalized = normalizeSvgDataUris(svgMarkup)
  try {
    const parser = new DOMParser()
    const doc = parser.parseFromString(normalized, 'image/svg+xml')
    const svg = doc.documentElement
    if (svg.tagName.toLowerCase() !== 'svg') return normalized

    const size = readSvgNaturalSizeFromElement(svg)
    if (!svg.getAttribute('viewBox') && size.width > 0 && size.height > 0) {
      svg.setAttribute('viewBox', `0 0 ${size.width} ${size.height}`)
    }
    svg.removeAttribute('width')
    svg.removeAttribute('height')
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet')
    return new XMLSerializer().serializeToString(svg)
  } catch {
    return normalized
  }
}

function readSvgNaturalSizeFromElement(svg: Element): SvgNaturalSize {
  const viewBox = svg.getAttribute('viewBox')
  if (viewBox) {
    const parts = viewBox.split(/[\s,]+/).map((value) => Number.parseFloat(value))
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      return { width: parts[2], height: parts[3] }
    }
  }
  const width = parseSvgLength(svg.getAttribute('width'))
  const height = parseSvgLength(svg.getAttribute('height'))
  return {
    width: width > 0 ? width : 800,
    height: height > 0 ? height : 600,
  }
}

function parseSvgLength(raw: string | null): number {
  if (!raw) return 0
  const value = Number.parseFloat(raw.replace(/[^\d.]/g, ''))
  return Number.isFinite(value) ? value : 0
}

export function readSvgNaturalSize(svgMarkup: string): SvgNaturalSize {
  try {
    const parser = new DOMParser()
    const doc = parser.parseFromString(svgMarkup, 'image/svg+xml')
    return readSvgNaturalSizeFromElement(doc.documentElement)
  } catch {
    return { width: 800, height: 600 }
  }
}

export function createSvgObjectUrl(svgMarkup: string): string {
  const prepared = prepareSvgForDisplay(svgMarkup)
  return URL.createObjectURL(new Blob([prepared], { type: 'image/svg+xml;charset=utf-8' }))
}
