import { ElMessage } from 'element-plus'

const unauthorizedHandlers = new Set()

export function onUnauthorized(fn) {
  unauthorizedHandlers.add(fn)
}

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.status = status
    this.detail = detail
  }
}

export async function api(path, { method = 'GET', body, quiet = false } = {}) {
  const options = {
    method,
    credentials: 'same-origin',
    headers: {}
  }
  if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }
  let res
  try {
    res = await fetch('/api' + path, options)
  } catch (e) {
    const err = new ApiError('无法连接后端服务', 0, null)
    if (!quiet) ElMessage.error(err.message)
    throw err
  }
  const data = await res.json().catch(() => null)
  if (res.status === 401) {
    unauthorizedHandlers.forEach((fn) => fn())
  }
  if (!res.ok) {
    const err = new ApiError(data?.message || `请求失败 (${res.status})`, res.status, data?.detail)
    if (!quiet) ElMessage.error(err.message)
    throw err
  }
  return data
}

export const apiGet = (path, opts) => api(path, opts)
export const apiPost = (path, body, opts) => api(path, { ...opts, method: 'POST', body })
export const apiPut = (path, body, opts) => api(path, { ...opts, method: 'PUT', body })
export const apiDelete = (path, opts) => api(path, { ...opts, method: 'DELETE' })