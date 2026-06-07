export function formatDateTimeCN(value, timeZone = 'Asia/Shanghai') {
  if (!value) return '—'
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return String(value).replace('T', ' ').slice(0, 16)
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(date).replace(/\//g, '-')
  } catch {
    return String(value).replace('T', ' ').slice(0, 16)
  }
}
