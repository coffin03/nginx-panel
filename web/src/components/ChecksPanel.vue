<template>
  <div class="checks-panel">
    <div class="toolbar">
      <el-button size="small" :icon="Refresh" :loading="loading" @click="load">{{ t('check.run') }}</el-button>
      <span v-if="report" class="muted small">
        {{ t('check.summary', { error: report.summary.error, warning: report.summary.warning, info: report.summary.info }) }}
      </span>
      <span class="grow"></span>
      <span v-if="report && !report.items.length" class="ok small">{{ t('check.ok') }}</span>
    </div>

    <el-alert
      v-if="report && !report.items.length"
      type="success"
      :closable="false"
      show-icon
      :title="t('check.ok')"
    />

    <div v-else-if="report" class="panel table-wrap">
      <el-table :data="report.items" size="small" style="width: 100%">
        <el-table-column :label="t('check.level')" width="90">
          <template #default="{ row }">
            <el-tag :type="tagType(row.level)" size="small" effect="plain">{{ levelLabel(row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('check.message')" min-width="320">
          <template #default="{ row }">
            <span class="small">{{ row.message }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('check.location')" min-width="260">
          <template #default="{ row }">
            <div v-if="row.file" class="mono tiny path" :title="row.file">{{ row.file }}</div>
            <div v-if="row.line" class="muted tiny">{{ t('check.line', { n: row.line }) }}</div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-else-if="!loading" class="empty-hint panel">{{ t('check.empty') }}</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import { apiGet } from '../api'
import { holdLoading } from '../utils/busy'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const { t } = useI18n()

const report = ref(null)
const loading = ref(false)

function tagType(level) {
  return { error: 'danger', warning: 'warning', info: 'info' }[level] || 'info'
}

function levelLabel(level) {
  return t(`check.level${level.charAt(0).toUpperCase()}${level.slice(1)}`)
}

async function load() {
  const started = Date.now()
  loading.value = true
  try {
    report.value = await apiGet(`/instances/${props.instanceId}/checks`)
  } catch (e) {
    report.value = null
  } finally {
    await holdLoading(started)
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.checks-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  min-height: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: none;
}
.table-wrap {
  padding: 6px 8px;
  overflow: auto;
}
.small {
  font-size: 12px;
}
.tiny {
  font-size: 11px;
  margin-top: 2px;
}
.path {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ok {
  color: var(--el-color-success);
}
.muted {
  color: var(--ngp-muted);
}
.empty-hint {
  padding: 28px;
  text-align: center;
  color: var(--ngp-muted);
}
</style>