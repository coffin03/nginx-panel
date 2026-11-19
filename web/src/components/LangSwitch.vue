<template>
  <el-dropdown trigger="click" @command="change">
    <button class="lang-btn" type="button" :title="t('lang.title')" :aria-label="t('lang.title')">
      <span class="lang-text">{{ locale === 'en' ? 'EN' : '中' }}</span>
      <el-icon :size="12"><CaretBottom /></el-icon>
    </button>
    <template #dropdown>
      <el-dropdown-menu>
        <el-dropdown-item command="zh" :class="{ on: locale === 'zh' }">中文</el-dropdown-item>
        <el-dropdown-item command="en" :class="{ on: locale === 'en' }">English</el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { CaretBottom } from '@element-plus/icons-vue'
import { setLocale } from '../i18n'

const { t, locale } = useI18n()

function change(value) {
  setLocale(value)
}
</script>

<style scoped>
.lang-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 34px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid var(--ngp-border);
  background: var(--ngp-surface);
  color: var(--ngp-text-2);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.2s ease, border-color 0.2s ease;
}
.lang-btn:hover {
  color: var(--ngp-brand);
  border-color: var(--ngp-brand);
}
.lang-text {
  min-width: 14px;
  text-align: center;
}
.on {
  color: var(--ngp-brand);
  font-weight: 600;
}
</style>