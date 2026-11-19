<template>
  <el-config-provider :locale="elLocale">
    <div class="app-shell">
      <header v-if="auth.authenticated" class="app-header">
        <div class="brand" @click="$router.push('/')">
          <img class="brand-logo" src="/favicon.svg" alt="logo" />
          <span class="brand-name">nginx<span class="accent">-panel</span></span>
        </div>
        <span class="brand-sub">{{ t('app.subtitle') }}</span>
        <div class="grow" />
        <LangSwitch />
        <ThemeSwitch />
        <div class="user-chip">
          <el-icon :size="14"><User /></el-icon>
          <span class="user-name">{{ auth.username }}</span>
        </div>
        <el-button link class="logout" :loading="loggingOut" @click="logout">{{ t('app.logout') }}</el-button>
      </header>
      <router-view />
    </div>
  </el-config-provider>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import enUs from 'element-plus/es/locale/lang/en'
import { User } from '@element-plus/icons-vue'
import LangSwitch from './components/LangSwitch.vue'
import ThemeSwitch from './components/ThemeSwitch.vue'
import { auth, refreshAuth } from './store'
import { apiPost, onUnauthorized } from './api'

const router = useRouter()
const { t, locale } = useI18n()
const elLocale = computed(() => (locale.value === 'en' ? enUs : zhCn))
const loggingOut = ref(false)

onMounted(async () => {
  onUnauthorized(() => {
    auth.authenticated = false
    router.push('/login')
  })
  try {
    await refreshAuth()
  } catch (e) {
    /* 后端未启动时静默 */
  }
})

async function logout() {
  loggingOut.value = true
  try {
    await apiPost('/auth/logout')
  } finally {
    loggingOut.value = false
    auth.authenticated = false
    router.push('/login')
    ElMessage.success(t('app.loggedOut'))
  }
}
</script>

<style scoped>
.app-shell {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}
.app-header {
  height: 60px;
  padding: 0 26px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: color-mix(in srgb, var(--ngp-surface) 82%, transparent);
  backdrop-filter: saturate(180%) blur(14px);
  -webkit-backdrop-filter: saturate(180%) blur(14px);
  border-bottom: 1px solid var(--ngp-border-soft);
  position: sticky;
  top: 0;
  z-index: 20;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.brand-logo {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: block;
  box-shadow: 0 6px 16px -10px var(--ngp-brand);
  transition: transform 0.2s ease;
}
.brand:hover .brand-logo {
  transform: translateY(-1px) scale(1.04);
}
.brand-name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.2px;
  color: var(--ngp-text);
}
.accent {
  color: var(--ngp-brand);
}
.brand-sub {
  font-size: 12px;
  color: var(--ngp-muted);
  padding-left: 12px;
  border-left: 1px solid var(--ngp-border);
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border);
  color: var(--ngp-text-2);
  font-size: 13px;
}
.user-name {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.logout {
  font-size: 13px;
  color: var(--ngp-muted);
}
.logout:hover {
  color: var(--ngp-brand);
}
@media (max-width: 720px) {
  .brand-sub,
  .user-name {
    display: none;
  }
  .app-header {
    padding: 0 16px;
  }
}
</style>