<template>
  <div class="file-tree">
    <div class="tree-tools">
      <el-input v-model="keyword" size="small" :placeholder="t('fileTree.search')" clearable :prefix-icon="Search" />
      <el-checkbox v-model="onlyConfig" size="small">{{ t('fileTree.onlyConfig') }}</el-checkbox>
    </div>
    <div class="tree-list">
      <div v-for="group in groups" :key="group.dir" class="group">
        <div class="group-title mono">{{ group.dir }}</div>
        <div
          v-for="file in group.files"
          :key="file.path"
          class="file-item"
          :class="{ active: file.path === active }"
          @click="$emit('select', file)"
        >
          <div class="file-main">
            <el-icon class="file-icon"><Document /></el-icon>
            <span class="file-name" :title="file.path">{{ file.name }}</span>
          </div>
          <div class="file-tags">
            <el-tag v-if="file.is_main" size="small" type="success" effect="plain">{{ t('fileTree.main') }}</el-tag>
            <el-tag v-else-if="file.included" size="small" type="primary" effect="plain">{{ t('fileTree.included') }}</el-tag>
            <el-tag v-if="!file.editable" size="small" type="info" effect="plain">{{ t('fileTree.readonly') }}</el-tag>
            <span class="file-size">{{ humanSize(file.size) }}</span>
          </div>
        </div>
      </div>
      <div v-if="!groups.length" class="empty-hint">{{ t('fileTree.empty') }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Document, Search } from '@element-plus/icons-vue'

const props = defineProps({
  files: { type: Array, default: () => [] },
  active: { type: String, default: '' }
})
defineEmits(['select'])
const { t } = useI18n()

const keyword = ref('')
const onlyConfig = ref(true)

const groups = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const filtered = props.files.filter((file) => {
    if (onlyConfig.value && !file.included && !file.is_main) return false
    if (!kw) return true
    return file.rel.toLowerCase().includes(kw)
  })
  const map = new Map()
  for (const file of filtered) {
    const idx = file.rel.lastIndexOf('/')
    const dir = idx >= 0 ? file.rel.slice(0, idx) : '.'
    if (!map.has(dir)) map.set(dir, [])
    map.get(dir).push(file)
  }
  return [...map.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([dir, files]) => ({
      dir,
      files: files.sort((a, b) => a.name.localeCompare(b.name))
    }))
})

function humanSize(size) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.file-tree {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.tree-tools {
  padding: 10px;
  border-bottom: 1px solid var(--ngp-border-soft);
  background: var(--ngp-surface-2);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tree-list {
  flex: 1;
  overflow: auto;
  padding: 8px 8px 16px;
}
.group-title {
  font-size: 11px;
  letter-spacing: 0.3px;
  color: var(--ngp-muted);
  padding: 10px 8px 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  border-left: 2px solid transparent;
  transition: background-color 0.18s ease, color 0.18s ease;
}
.file-item:hover {
  background: var(--ngp-surface-3);
}
.file-item.active {
  background: var(--ngp-brand-soft);
  border-left-color: var(--ngp-brand);
  color: var(--ngp-brand-strong);
  font-weight: 500;
}
.file-item.active .file-icon {
  color: var(--ngp-brand);
}
.file-main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.file-icon {
  color: var(--ngp-muted);
  flex: none;
}
.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-tags {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: none;
}
.file-size {
  font-size: 11px;
  color: var(--ngp-muted);
}
.empty-hint {
  padding: 24px 12px;
}
</style>