<template>
  <el-dropdown trigger="click" @command="setTheme">
    <button class="theme-btn" type="button" :title="t('theme.title', { label })" :aria-label="t('theme.aria')">
      <el-icon :size="17"><component :is="icon" /></el-icon>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="light" :class="{ on: theme.mode === 'light' }">
          <el-icon><Sunny /></el-icon>{{ t('theme.light') }}
        </el-dropdown-item>
        <el-dropdown-item command="dark" :class="{ on: theme.mode === 'dark' }">
          <el-icon><Moon /></el-icon>{{ t('theme.dark') }}
        </el-dropdown-item>
        <el-dropdown-item command="system" :class="{ on: theme.mode === 'system' }" divided>
          <el-icon><Monitor /></el-icon>{{ t('theme.system') }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Monitor, Moon, Sunny } from '@element-plus/icons-vue'
import { effective, setTheme, theme } from '../theme'

const { t } = useI18n()
const icon = computed(() => (effective.value === 'dark' ? Moon : theme.mode === 'system' ? Monitor : Sunny))
const label = computed(() => t(`theme.${theme.mode}`))
</script>

<style scoped>
.theme-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border-radius: 10px;
  border: 1px solid var(--ngp-border);
  background: var(--ngp-surface);
  color: var(--ngp-text-2);
  cursor: pointer;
  transition: color 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
}
.theme-btn:hover {
  color: var(--ngp-brand);
  border-color: var(--ngp-brand);
}
.on {
  color: var(--ngp-brand);
  font-weight: 600;
}
</style>