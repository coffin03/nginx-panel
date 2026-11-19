import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN'
import enUS from './locales/en-US'

const STORAGE_KEY = 'ngp-locale'
const SUPPORTED = ['zh', 'en']

function storedLocale() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (SUPPORTED.includes(saved)) return saved
    // 兼容浏览器语言：仅当用户没有保存过偏好时生效，默认中文
    const nav = (navigator.language || '').toLowerCase()
    return nav.startsWith('en') ? 'en' : 'zh'
  } catch (e) {
    return 'zh'
  }
}

const i18n = createI18n({
  legacy: false,
  locale: storedLocale(),
  fallbackLocale: 'zh',
  messages: { zh: zhCN, en: enUS }
})

export function setLocale(locale) {
  const next = SUPPORTED.includes(locale) ? locale : 'zh'
  i18n.global.locale.value = next
  try {
    localStorage.setItem(STORAGE_KEY, next)
  } catch (e) {
    /* 隐私模式下忽略 */
  }
  document.documentElement.setAttribute('lang', next === 'en' ? 'en' : 'zh-CN')
}

export function currentLocale() {
  return i18n.global.locale.value
}

setLocale(i18n.global.locale.value)

export default i18n