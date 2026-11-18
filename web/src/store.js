import { reactive } from 'vue'
import { api } from './api'

export const auth = reactive({
  checked: false,
  initialized: false,
  authenticated: false,
  username: null
})

export async function refreshAuth() {
  const data = await api('/auth/status', { quiet: true })
  auth.initialized = data.initialized
  auth.authenticated = data.authenticated
  auth.username = data.username
  auth.checked = true
  return data
}