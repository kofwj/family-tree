import api from '../api/client'

export async function fetchAuthenticatedObjectUrl(url) {
  if (!url) return ''
  const apiPath = url.startsWith('/api/') ? url.slice(4) : url
  const { data } = await api.get(apiPath, { responseType: 'blob' })
  return URL.createObjectURL(data)
}

export function revokeObjectUrl(url) {
  if (url && url.startsWith('blob:')) URL.revokeObjectURL(url)
}
