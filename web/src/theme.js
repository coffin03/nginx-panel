import { computed, reactive } from 'vue'

const KEY = 'ngp-theme'
const media = window.matchMedia('(prefers-color-scheme: dark)')

const saved = localStorage.getItem(KEY)
const initial = ['light', 'dark', 'system'].includes(saved) ? saved : 'system'

export const theme = reactive({
  mode: initial,
  systemDark: media.matches
})

export const effective = computed(() => (theme.mode === 'system' ? (theme.systemDark ? 'dark' : 'light') : theme.mode))

export function applyTheme() {
  const dark = effective.value === 'dark'
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

export function setTheme(mode) {
  theme.mode = mode
  localStorage.setItem(KEY, mode)
  applyTheme()
}

media.addEventListener('change', (event) => {
  theme.systemDark = event.matches
  if (theme.mode === 'system') applyTheme()
})

applyTheme()