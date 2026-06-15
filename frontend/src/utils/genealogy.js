export const FAMILY_HUE_PRESETS = {
  '王': 32,   // Warm Amber / Bronze (王氏家族)
  '孙': 210,  // Ocean Blue (孙氏家族)
  '顾': 140,  // Jade Green (顾氏家族)
  '曹': 280,  // Deep Violet / Purple (曹氏家族)
  '周': 345,  // Rose Red (周氏家族)
  '季': 45,   // Golden Yellow (季氏家族)
  '成': 80,   // Olive / Sage Green (成氏家族)
  '洪': 175,  // Muted Teal / Cyan (洪氏家族)
  '张': 250,  // Indigo Blue (张氏家族)
  '陈': 15    // Terracotta (陈氏家族)
}

export function getFamilySurname(name) {
  if (!name) return '王'
  let s = String(name).replace(/(氏家族|氏宗族|氏族|宗族|家族|家谱)/g, '')
  return s.charAt(0) || '王'
}

export function getBaseHueForSurname(surname) {
  const char = String(surname || '').charAt(0)
  if (FAMILY_HUE_PRESETS[char] !== undefined) {
    return FAMILY_HUE_PRESETS[char]
  }
  let hash = 0
  for (let i = 0; i < char.length; i++) {
    hash = char.charCodeAt(i) + ((hash << 5) - hash)
  }
  return Math.abs(hash) % 360
}

export function generateFamilyPalette(baseHue) {
  const palette = []
  const variations = [
    { hOff: 0,   s: 36, l: 48 }, // 1. Muted Base
    { hOff: 8,   s: 30, l: 56 }, // 2. Lighter Analogous
    { hOff: -8,  s: 42, l: 42 }, // 3. Deeper Muted
    { hOff: 15,  s: 26, l: 62 }, // 4. Soft Pastel
    { hOff: -15, s: 32, l: 46 }, // 5. Slate Muted
    { hOff: 4,   s: 34, l: 52 }, // 6. Gentle Medium
    { hOff: -4,  s: 38, l: 44 }, // 7. Richer Analogous
    { hOff: 12,  s: 28, l: 60 }  // 8. Softest Light
  ]
  for (const v of variations) {
    const h = (baseHue + v.hOff + 360) % 360
    palette.push(`hsl(${h}, ${v.s}%, ${v.l}%)`)
  }
  return palette
}
