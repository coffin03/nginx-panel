<template>
  <div class="sites-panel">
    <div class="toolbar">
      <el-button size="small" :icon="Refresh" :loading="loading" @click="load">{{ t('common.refresh') }}</el-button>
      <span v-if="sites.length" class="muted small">{{ t('site.listCount', { n: sites.length }) }}</span>
      <span class="grow"></span>
      <span v-if="!loading && sites.length && !includeConfigured" class="warn small">
        {{ t('site.includeMissing') }}
      </span>
    </div>

    <div v-if="!loading && !sites.length" class="empty-hint panel">{{ t('site.empty') }}</div>

    <div v-else class="panel table-wrap">
      <el-table :data="sites" size="small" style="width: 100%">
        <el-table-column :label="t('site.colFile')" min-width="190">
          <template #default="{ row }">
            <div class="mono small">{{ row.name }}</div>
            <div class="muted tiny">{{ row.rel }}</div>
            <div v-if="row.parse_error" class="error tiny">{{ row.parse_error }}</div>
          </template>
        </el-table-column>
        <el-table-column :label="t('site.colDomains')" min-width="190">
          <template #default="{ row }">
            <div class="domains">
              <span v-for="name in row.server_names" :key="name" class="domain mono">{{ name }}</span>
              <span v-if="!row.server_names.length" class="muted">—</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('site.colListen')" width="90">
          <template #default="{ row }">
            <span class="mono small">{{ row.listens.join(', ') || '80' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('site.colKind')" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.kind" size="small" effect="plain">{{ kindLabel(row.kind) }}</el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('site.colCert')" min-width="150">
          <template #default="{ row }">
            <span class="mono small path" :title="row.certificate">{{ row.certificate || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('site.colStatus')" width="130">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small" effect="plain">
              {{ row.enabled ? t('site.enabled') : t('site.disabled') }}
            </el-tag>
            <el-tag v-if="row.enabled && !row.loaded" type="warning" size="small" effect="plain" class="ml">
              {{ t('site.notLoaded') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('site.colActions')" width="196" align="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :loading="rowBusy(row, 'edit')" @click="openEdit(row)">{{ t('site.edit') }}</el-button>
            <el-button link type="primary" size="small" :loading="rowBusy(row, 'toggle')" @click="toggle(row)">
              {{ row.enabled ? t('site.disable') : t('site.enable') }}
            </el-button>
            <el-button link type="danger" size="small" :loading="rowBusy(row, 'delete')" @click="remove(row)">{{ t('common.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="editVisible" :title="t('site.editTitle')" width="820px" top="6vh">
      <div class="edit-body">
        <div class="edit-meta">
          <span class="mono small">{{ editRow?.rel }}</span>
          <span class="muted tiny">{{ t('site.editTip') }}</span>
        </div>
        <div v-if="editRow?.ssl" class="cert-bar">
          <el-select v-model="certPath" size="small" filterable clearable class="cert-select" :placeholder="t('site.certificate')">
            <el-option v-for="c in certs" :key="c.path" :label="c.domains.join(', ') || c.path" :value="c.path" />
          </el-select>
          <el-input v-model="keyPath" size="small" class="cert-select" :placeholder="t('site.certificateKey')" />
          <el-button size="small" @click="applyCert">{{ t('site.applyCert') }}</el-button>
        </div>
        <CodeEditor v-model="editContent" class="editor" />
      </div>
      <template #footer>
        <el-button @click="editVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { apiDelete, apiGet, apiPost, apiPut } from '../api'
import { holdLoading } from '../utils/busy'
import CodeEditor from './CodeEditor.vue'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const emit = defineEmits(['changed'])
const { t } = useI18n()

const sites = ref([])
const includeConfigured = ref(true)
const loading = ref(false)

const editVisible = ref(false)
const editRow = ref(null)
const editContent = ref('')
const editHash = ref('')
const saving = ref(false)
const busyRow = ref('')
const certs = ref([])
const certPath = ref('')
const keyPath = ref('')

function kindLabel(kind) {
  return kind === 'proxy' ? t('site.kindProxy') : t('site.kindStatic')
}

function rowBusy(row, action) {
  return busyRow.value === `${row.name}:${action}`
}

async function load() {
  const started = Date.now()
  loading.value = true
  try {
    const res = await apiGet(`/instances/${props.instanceId}/sites`)
    sites.value = res.sites || []
    includeConfigured.value = res.include_configured !== false
  } catch (e) {
    sites.value = []
  } finally {
    await holdLoading(started)
    loading.value = false
  }
}

async function openEdit(row) {
  busyRow.value = `${row.name}:edit`
  editRow.value = row
  editContent.value = ''
  editHash.value = ''
  certPath.value = ''
  keyPath.value = ''
  editVisible.value = true
  try {
    const info = await apiGet(
      `/instances/${props.instanceId}/file?path=${encodeURIComponent(row.rel)}`
    )
    editContent.value = info.content || ''
    editHash.value = info.hash || ''
    if (row.ssl) await loadCerts()
  } catch (e) {
    editVisible.value = false
  } finally {
    busyRow.value = ''
  }
}

async function loadCerts() {
  try {
    const res = await apiGet(`/instances/${props.instanceId}/certificates`)
    certs.value = res.certificates || []
  } catch (e) {
    certs.value = []
  }
}

function applyCert() {
  const cert = certPath.value.trim()
  const key = keyPath.value.trim()
  if (!cert && !key) return
  let text = editContent.value
  let hit = false
  if (cert && /^\s*ssl_certificate\s+/m.test(text)) {
    text = text.replace(/(^\s*ssl_certificate\s+)([^;]+);/m, (m, head) => `${head}${cert};`)
    hit = true
  }
  if (key && /^\s*ssl_certificate_key\s+/m.test(text)) {
    text = text.replace(/(^\s*ssl_certificate_key\s+)([^;]+);/m, (m, head) => `${head}${key};`)
    hit = true
  }
  if (!hit) {
    ElMessage.warning(t('site.noSslLine'))
    return
  }
  editContent.value = text
  ElMessage.success(t('site.certApplied'))
}

async function save() {
  saving.value = true
  try {
    await apiPut(`/instances/${props.instanceId}/file`, {
      path: editRow.value.rel,
      content: editContent.value,
      base_hash: editHash.value || null,
      message: t('site.editMessage', { name: editRow.value.name }),
      reload: true
    })
    ElMessage.success(t('site.saved'))
    editVisible.value = false
    await load()
    emit('changed')
  } catch (e) {
    /* 全局提示已展示 */
  } finally {
    saving.value = false
  }
}

async function toggle(row) {
  const action = row.enabled ? 'disable' : 'enable'
  busyRow.value = `${row.name}:toggle`
  try {
    await apiPost(`/instances/${props.instanceId}/sites/${encodeURIComponent(row.name)}/${action}`)
    ElMessage.success(t('site.toggled'))
    await load()
    emit('changed')
  } catch (e) {
    /* 全局提示已展示 */
  } finally {
    busyRow.value = ''
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(t('site.deleteConfirm', { name: row.name }), t('site.deleteTitle'), {
      type: 'warning',
      confirmButtonText: t('common.delete'),
      cancelButtonText: t('common.cancel')
    })
  } catch (e) {
    return
  }
  busyRow.value = `${row.name}:delete`
  try {
    await apiDelete(`/instances/${props.instanceId}/sites/${encodeURIComponent(row.name)}`)
    ElMessage.success(t('site.deleted'))
    await load()
    emit('changed')
  } catch (e) {
    /* 全局提示已展示 */
  } finally {
    busyRow.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.sites-panel {
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
.domains {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.domain {
  font-size: 11.5px;
  padding: 1px 7px;
  border-radius: 6px;
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border-soft);
}
.path {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.small {
  font-size: 12px;
}
.tiny {
  font-size: 11px;
  margin-top: 2px;
}
.error {
  color: var(--el-color-danger);
  word-break: break-all;
}
.warn {
  color: var(--el-color-warning);
}
.muted {
  color: var(--ngp-muted);
}
.ml {
  margin-left: 4px;
}
.empty-hint {
  padding: 28px;
  text-align: center;
  color: var(--ngp-muted);
}
.edit-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.edit-meta {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}
.cert-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cert-select {
  flex: 1;
}
.editor {
  height: 340px;
  border: 1px solid var(--ngp-border-soft);
  border-radius: 8px;
  overflow: hidden;
}
</style>