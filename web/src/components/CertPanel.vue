<template>
  <div class="cert-panel">
    <div class="toolbar">
      <el-button size="small" :icon="Refresh" :loading="loading" @click="load">{{ t('common.refresh') }}</el-button>
      <span v-if="certs.length" class="muted small">{{ t('cert.count', { n: certs.length }) }}</span>
      <span class="grow"></span>
      <span v-if="attention" class="warn small">{{ t('cert.attention', { n: attention }) }}</span>
    </div>

    <div v-if="!loading && !certs.length" class="empty-hint panel">{{ t('cert.empty') }}</div>

    <div v-else class="panel table-wrap">
      <el-table :data="certs" size="small" style="width: 100%">
        <el-table-column :label="t('cert.domains')" min-width="210">
          <template #default="{ row }">
            <div class="domains">
              <span v-for="name in row.domains || []" :key="name" class="domain mono">{{ name }}</span>
              <span v-if="!(row.domains || []).length" class="muted">—</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('cert.expires')" width="230">
          <template #default="{ row }">
            <div class="expiry">
              <el-tag :type="tagType(row.status)" size="small" effect="plain">{{ statusLabel(row.status) }}</el-tag>
              <span v-if="row.not_after" class="mono small">{{ row.not_after.slice(0, 10) }}</span>
              <span v-if="typeof row.days_left === 'number'" class="muted small">{{ daysLabel(row) }}</span>
            </div>
            <div v-if="row.error" class="error small">{{ row.error }}</div>
          </template>
        </el-table-column>
        <el-table-column :label="t('cert.issuer')" min-width="150">
          <template #default="{ row }">
            <span class="muted small">{{ row.issuer || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('cert.path')" min-width="240">
          <template #default="{ row }">
            <div class="mono small path" :title="row.path">{{ row.path }}</div>
            <div class="muted tiny">{{ t('cert.source', { file: row.file, line: row.line }) }}</div>
          </template>
        </el-table-column>
        <el-table-column :label="t('cert.actions')" width="90" align="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :loading="renewing === row.path" @click="openRenew(row)">{{ t('cert.renew') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="renewVisible" :title="t('cert.renewTitle')" width="680px" top="8vh">
      <div class="renew-body">
        <div class="renew-meta">
          <div class="mono small">{{ renewRow?.path }}</div>
          <div class="muted small">
            {{ t('cert.renewFromTo', { before: renewRow?.not_after?.slice(0, 10) || '—', after: '…' }) }}
          </div>
        </div>

        <el-form label-width="96px" size="small" label-position="left">
          <el-form-item :label="t('cert.renewTool')">
            <el-select v-model="toolId" style="width: 100%" @change="onToolChange">
              <el-option v-for="opt in options" :key="opt.id" :label="opt.label" :value="opt.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('cert.renewReload')">
            <el-switch v-model="reloadAfter" />
          </el-form-item>
        </el-form>

        <el-input v-model="command" type="textarea" :rows="3" class="mono" spellcheck="false" />
        <div class="muted tiny hint">{{ t('cert.renewHint') }}</div>

        <div v-if="result" class="result">
          <el-alert :type="result.changed ? 'success' : 'warning'" :closable="false" :title="resultTitle" show-icon />
          <div v-if="resultMeta" class="muted small meta">{{ resultMeta }}</div>
          <div v-if="result.reload && !result.reload.ok" class="error small">{{ t('cert.reloadFailed') }}</div>
          <div class="output-label muted tiny">{{ t('cert.renewOutput') }}</div>
          <pre class="output mono">{{ result.output || t('common.noOutput') }}</pre>
        </div>
      </div>

      <template #footer>
        <el-button @click="renewVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="running" @click="runRenew">{{ t('cert.renewRun') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { apiGet, apiPost } from '../api'
import { holdLoading } from '../utils/busy'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const { t } = useI18n()

const certs = ref([])
const loading = ref(false)

const renewVisible = ref(false)
const renewRow = ref(null)
const options = ref([])
const toolId = ref('custom')
const command = ref('')
const reloadAfter = ref(true)
const running = ref(false)
const renewing = ref('')
const result = ref(null)

const attention = computed(() => certs.value.filter((c) => c.status !== 'ok').length)

const resultTitle = computed(() => {
  if (!result.value) return ''
  if (!result.value.ok) return t('cert.renewFailed', { code: result.value.exit_code })
  return result.value.changed ? t('cert.renewChanged') : t('cert.renewUnchanged')
})

const resultMeta = computed(() => {
  const before = result.value?.before?.not_after?.slice(0, 10) || '—'
  const after = result.value?.after?.not_after?.slice(0, 10) || '—'
  return result.value ? t('cert.renewFromTo', { before, after }) : ''
})

function onToolChange(id) {
  const opt = options.value.find((item) => item.id === id)
  if (opt && opt.command) command.value = opt.command
}

async function openRenew(row) {
  renewing.value = row.path
  renewRow.value = row
  result.value = null
  options.value = []
  command.value = ''
  renewVisible.value = true
  try {
    const res = await apiGet(
      `/instances/${props.instanceId}/certificates/renew-options?path=${encodeURIComponent(row.path)}`
    )
    options.value = res.options || []
    const first = options.value.find((item) => item.command)
    if (first) {
      toolId.value = first.id
      command.value = first.command
    } else {
      toolId.value = 'custom'
    }
  } catch (e) {
    options.value = [{ id: 'custom', label: t('cert.renewCustom'), command: '' }]
    toolId.value = 'custom'
  } finally {
    renewing.value = ''
  }
}

async function runRenew() {
  running.value = true
  try {
    result.value = await apiPost(`/instances/${props.instanceId}/certificates/renew`, {
      path: renewRow.value.path,
      command: command.value,
      reload: reloadAfter.value
    })
    if (result.value.changed) await load()
    if (result.value.changed && result.value.reload && !result.value.reload.ok) {
      ElMessage.warning(t('cert.reloadFailed'))
    }
  } catch (e) {
    /* 错误已由全局提示 */
  } finally {
    running.value = false
  }
}

function tagType(status) {
  return { ok: 'success', warning: 'warning', expired: 'danger', missing: 'danger', invalid: 'info' }[status] || 'info'
}

function statusLabel(status) {
  return t(`cert.status${status.charAt(0).toUpperCase()}${status.slice(1)}`)
}

function daysLabel(row) {
  return row.days_left < 0 ? t('cert.expired', { n: -row.days_left }) : t('cert.daysLeft', { n: row.days_left })
}

async function load() {
  const started = Date.now()
  loading.value = true
  try {
    const res = await apiGet(`/instances/${props.instanceId}/certificates`)
    certs.value = res.certificates || []
  } catch (e) {
    certs.value = []
  } finally {
    await holdLoading(started)
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.cert-panel {
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
.expiry {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.path {
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
  margin-top: 4px;
  word-break: break-all;
}
.warn {
  color: var(--el-color-warning);
}
.muted {
  color: var(--ngp-muted);
}
.empty-hint {
  padding: 28px;
  text-align: center;
  color: var(--ngp-muted);
}
.renew-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.renew-meta {
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border-soft);
  word-break: break-all;
}
.hint {
  margin-top: -4px;
  line-height: 1.5;
}
.result {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 4px;
  border-top: 1px dashed var(--ngp-border-soft);
}
.meta {
  margin-top: 2px;
}
.output-label {
  margin-top: 4px;
}
.output {
  margin: 0;
  padding: 8px 10px;
  max-height: 220px;
  overflow: auto;
  border-radius: 8px;
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border-soft);
  font-size: 11.5px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>