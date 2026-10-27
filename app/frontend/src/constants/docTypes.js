// 文种名称映射，用于列表等处只需显示名称的场景。
// 完整配置（段落结构、结束语等）由后端 /api/documents/doc-types 提供。

export const DOC_TYPE_NAMES = {
  request: '请示',
  report: '报告',
  notice: '通知',
  circular: '通报',
  reply: '批复',
  decision: '决定',
  opinion: '意见',
  letter: '函',
  minutes: '纪要',
}

export function docTypeName(code) {
  return DOC_TYPE_NAMES[code] || '公文'
}

// 预览章节用的中文序号
export const CN_NUM = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']

export function cnNum(n) {
  return CN_NUM[n - 1] || String(n)
}
