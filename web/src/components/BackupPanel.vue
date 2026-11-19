<template>
  <div class="backup-panel">
    <div class="panel card">
      <div class="card-title">{{ t('backup.export') }}</div>
      <p class="muted small tip">{{ t('backup.tip') }}</p>
      <div class="actions">
        <el-button type="primary" :loading="exporting" @click="download">{{ t('backup.export') }}</el-button>
        <el-button :icon="Upload" :loading="inspecting" @click="pickFile">{{ t('backup.import') }}</el-button>
        <input ref="fileInput" type="file" accept=".zip,application/zip" hidden @change="onFile" />
      </div>
    </div>

    <div v-if="preview" class="panel card">
      <div class="preview-head">
        <div class="preview-title">
          <div class="card-title">{{ t('backup.dialogTitle') }}</div>
          <div class="muted small">
            <span v-if="preview.manifest.name">{{ t('backup.source') }}: {{ preview.manifest.name }}</span>
            <span v-if="preview.manifest.created_at"> · {{ t('backup.createdAt') }}: {{ preview.manifest.created_at }}</span>
            <span v-if="fileName"> · {{ fileName }}</span>
          </div>
        </div>
        <span class="grow"></span>
        <el-tag size="small" effect="plain">{{ t('backup.summary', preview.summary) }}</el-tag>
      </div>

      <el-alert
        v-for="(warn, i) in preview.warnings"
        :key="i"
        class="warn"
        type="warning"
        :closable="false"
        show-icon
        :title="warn"
      />

      <el-table :data="preview.files" size="small" max-height="360" class="file-table">
        <el-table-column prop="rel" :label="t('backup.file')" min-width="320" show-overflow-tooltip />
        <el-table-column :label="t('backup.size')" width="110">
          <template #default="{ row }">
            <span class="mono small">{{ sizeText(row.size) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('backup.status')" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="plain">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="foot">
        <el-checkbox v-model="reload">{{ t('backup.reload') }}</el-checkbox>
        <span class="grow"></span>
        <el-button @click="reset">{{ t('backup.cancel') }}</el-button>
        <el-button type="primary" :loading="importing" :disabled="!preview.files.length" @click="doImport">
          {{ t('backup.confirm') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import { apiPost } from '../api'
import { currentLocale } from '../i18n'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const emit = defineEmits(['applied'])
const { t } = useI18n()

const exporting = ref(false)
const importing = ref(false)
const inspecting = ref(false)
const preview = ref(null)
const payload = ref('')
const fileName = ref('')
const reload = ref(true)
const fileInput = ref(null)

function pickFile() {
  fileInput.value?.click()
}

function reset() {
  preview.value = null
  payload.value = ''
  fileName.value = ''
}

function sizeText(size) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function statusType(status) {
  return { new: 'success', changed: 'warning', unchanged: 'info' }[status] || 'info'
}

function statusLabel(status) {
  return (
    {
      new: t('backup.statusNew'),
      changed: t('backup.statusChanged'),
      unchanged: t('backup.statusUnchanged')
    }[status] || status
  )
}

// 分块转换，避免大文件时 String.fromCharCode.apply 参数过多
function toBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk))
  }
  return btoa(binary)
}

async function download() {
  exporting.value = true
  try {
    const res = await fetch(`/api/instances/${props.instanceId}/backup/export`, {
      credentials: 'same-origin',
      headers: { 'X-Locale': currentLocale() }
    })
    if (!res.ok) {
      const data = await res.json().catch(() => null)
      throw new Error(data?.message || t('errors.requestFailed', { status: res.status }))
    }
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') || ''
    const match = disposition.match(/filename="?([^";]+)"?/)
    const name = match ? match[1] : `nginx-backup-${props.instanceId}.zip`
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = name
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success(t('backup.exported'))
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    exporting.value = false
  }
}

async function onFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  inspecting.value = true
  try {
    payload.value = toBase64(await file.arrayBuffer())
    fileName.value = file.name
    preview.value = await apiPost(`/instances/${props.instanceId}/backup/inspect`, { data: payload.value })
    if (!preview.value.files.length) ElMessage.warning(t('backup.noFiles'))
  } catch (e) {
    reset()
  } finally {
    inspecting.value = false
  }
}

async function doImport() {
  if (!payload.value) {
    ElMessage.warning(t('backup.selectFirst'))
    return
  }
  importing.value = true
  try {
    const res = await apiPost(`/instances/${props.instanceId}/backup/import`, {
      data: payload.value,
      reload: reload.value
    })
    ElMessage.success(t('backup.imported'))
    reset()
    emit('applied', res)
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.backup-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 12px;
}
.card {
  padding: 16px 18px;
}
.card-title {
  font-size: 14px;
  font-weight: 600;
}
.tip {
  margin: 8px 0 14px;
  line-height: 1.7;
  max-width: 780px;
}
.small {
  font-size: 12px;
}
.actions {
  display: flex;
  gap: 10px;
}
.preview-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.preview-title {
  min-width: 0;
}
.warn {
  margin-bottom: 8px;
}
.file-table {
  border: 1px solid var(--ngp-border-soft);
  border-radius: 8px;
}
.foot {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}
.grow {
  flex: 1;
}
.muted {
  color: var(--ngp-muted);
}
</style>