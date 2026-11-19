<template>
  <div class="history-panel">
    <div class="toolbar">
      <el-button :icon="Refresh" :loading="loading" @click="load">{{ t('common.refresh') }}</el-button>
      <span class="muted">{{ t('history.tip') }}</span>
    </div>

    <el-table v-loading="loading" :data="snapshots" size="small" class="table" @row-click="openDetail">
      <el-table-column prop="created_at" :label="t('history.time')" width="165" />
      <el-table-column prop="message" :label="t('history.message')" min-width="200" show-overflow-tooltip />
      <el-table-column :label="t('history.trigger')" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ triggerLabel(row.trigger) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="operator" :label="t('history.operator')" width="110" align="center" />
      <el-table-column prop="file_count" :label="t('history.files')" width="70" align="center" />
      <el-table-column :label="t('history.test')" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.test_ok === 1" size="small" type="success">{{ t('history.pass') }}</el-tag>
          <el-tag v-else-if="row.test_ok === 0" size="small" type="danger">{{ t('history.fail') }}</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column :label="t('history.actions')" width="136" align="center">
        <template #default="{ row }">
          <div class="ops">
            <el-button size="small" text type="primary" :loading="viewId === row.id" @click.stop="openDetail(row)">{{ t('history.view') }}</el-button>
            <el-button size="small" text type="warning" :loading="restoreId === row.id" @click.stop="restore(row)">{{ t('history.restore') }}</el-button>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-hint">{{ t('history.empty') }}</div>
      </template>
    </el-table>

    <div class="ops-section">
      <div class="section-head">
        <span class="section-title">{{ t('history.opsTitle') }}</span>
        <span class="muted tiny">{{ t('history.opsTip') }}</span>
      </div>
      <el-table :data="operations" size="small" class="table">
        <el-table-column type="expand">
          <template #default="{ row }">
            <pre class="op-detail mono">{{ row.detail || t('common.noOutput') }}</pre>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" :label="t('history.time')" width="165" />
        <el-table-column :label="t('history.opAction')" width="130">
          <template #default="{ row }">{{ actionLabel(row.action) }}</template>
        </el-table-column>
        <el-table-column :label="t('history.result')" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.ok ? 'success' : 'danger'" size="small" effect="plain">
              {{ row.ok ? t('history.pass') : t('history.fail') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('history.opsSummary')" min-width="240">
          <template #default="{ row }">
            <span class="muted small">{{ firstLine(row.detail) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty-hint muted">{{ t('history.opsEmpty') }}</div>
        </template>
      </el-table>
    </div>

    <el-drawer v-model="drawer" :title="t('history.detailTitle')" size="60%" destroy-on-close append-to-body>
      <template v-if="detail">
        <div class="detail-head">
          <div>
            <div class="mono">{{ detail.created_at }} · {{ triggerLabel(detail.trigger) }}</div>
            <div class="muted">{{ detail.message }}</div>
          </div>
          <el-button type="warning" plain :loading="restoring" @click="restore(detail)">{{ t('history.restoreHere') }}</el-button>
        </div>
        <el-radio-group v-model="currentPath" size="small" class="file-tabs" @change="loadDiff">
          <el-radio-button v-for="file in detail.files" :key="file.path" :value="file.path">
            {{ shortName(file.path) }}
          </el-radio-button>
        </el-radio-group>
        <div class="diff-hint muted">
          <span class="mono">{{ currentPath }}</span>
          <span>{{ t('history.diffHint') }}</span>
        </div>
        <pre v-if="diff" class="diff-view"><span
          v-for="(line, idx) in diffLines"
          :key="idx"
          :class="line.cls"
        >{{ line.text }}</span></pre>
        <div v-else class="empty-hint">{{ diffLoading ? t('history.diffLoading') : t('history.diffSame') }}</div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { apiGet, apiPost } from '../api'
import { holdLoading } from '../utils/busy'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const emit = defineEmits(['restored'])
const { t, te } = useI18n()

const loading = ref(false)
const snapshots = ref([])
const operations = ref([])
const drawer = ref(false)
const detail = ref(null)
const currentPath = ref('')
const diff = ref('')
const diffLoading = ref(false)
const restoring = ref(false)
const viewId = ref(null)
const restoreId = ref(null)

const diffLines = computed(() => {
  return diff.value.split('\n').map((text) => {
    let cls = ''
    if (text.startsWith('+++') || text.startsWith('---') || text.startsWith('@@')) cls = 'meta'
    else if (text.startsWith('+')) cls = 'add'
    else if (text.startsWith('-')) cls = 'del'
    return { text: text + '\n', cls }
  })
})

function triggerLabel(trigger) {
  const key = `history.trigger${(trigger || 'other').replace(/^./, (c) => c.toUpperCase())}`
  return te(key) ? t(key) : trigger || t('history.triggerOther')
}

function shortName(path) {
  const parts = path.replace(/\\/g, '/').split('/')
  return parts.slice(-2).join('/')
}

async function load() {
  const started = Date.now()
  loading.value = true
  try {
    snapshots.value = await apiGet(`/instances/${props.instanceId}/snapshots?limit=100`)
  } catch (e) {
    /* 已提示 */
  } finally {
    await holdLoading(started)
    loading.value = false
  }
  loadOps()
}

async function loadOps() {
  try {
    operations.value = await apiGet(`/instances/${props.instanceId}/operations`)
  } catch (e) {
    operations.value = []
  }
}

const ACTION_KEYS = {
  start: 'ops.start',
  stop: 'ops.stop',
  reload: 'ops.reload',
  restart: 'ops.restart',
  test: 'ops.test',
  'renew-cert': 'history.opRenew'
}

function actionLabel(action) {
  const key = ACTION_KEYS[action]
  return key ? t(key) : action
}

function firstLine(detail) {
  const text = (detail || '').split('\n').find((line) => line.trim()) || ''
  return text.length > 120 ? text.slice(0, 120) + '…' : text
}

onMounted(load)

async function openDetail(row) {
  viewId.value = row.id
  try {
    detail.value = await apiGet(`/instances/${props.instanceId}/snapshots/${row.id}`)
    drawer.value = true
    diff.value = ''
    currentPath.value = detail.value.files?.[0]?.path || ''
    if (currentPath.value) await loadDiff()
  } catch (e) {
    /* 已提示 */
  } finally {
    viewId.value = null
  }
}

async function loadDiff() {
  if (!detail.value || !currentPath.value) return
  diffLoading.value = true
  try {
    const res = await apiGet(
      `/instances/${props.instanceId}/snapshots/${detail.value.id}/diff?path=${encodeURIComponent(currentPath.value)}`
    )
    diff.value = res.diff || ''
  } catch (e) {
    diff.value = ''
  } finally {
    diffLoading.value = false
  }
}

async function restore(row) {
  try {
    await ElMessageBox.confirm(t('history.confirm', { time: row.created_at }), t('history.confirmTitle'), {
      type: 'warning',
      confirmButtonText: t('history.confirmOk'),
      cancelButtonText: t('common.cancel')
    })
  } catch (e) {
    return
  }
  restoring.value = true
  restoreId.value = row.id
  try {
    const res = await apiPost(`/instances/${props.instanceId}/snapshots/${row.id}/restore`, { reload: true })
    ElMessage.success(res.reloaded ? t('history.restoredReloaded') : t('history.restored'))
    drawer.value = false
    await load()
    emit('restored', res)
  } catch (e) {
    /* 已提示 */
  } finally {
    restoring.value = false
    restoreId.value = null
  }
}
</script>

<style scoped>
.toolbar {
  padding-bottom: 10px;
}
.table {
  width: 100%;
}
.table :deep(.el-table__row) {
  cursor: pointer;
}
.ops {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  white-space: nowrap;
}
.ops :deep(.el-button) {
  margin-left: 0;
  padding: 4px 6px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}
.file-tabs {
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.diff-hint {
  font-size: 12px;
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.diff-view :deep(span),
.diff-view span {
  display: block;
  white-space: pre-wrap;
  word-break: break-all;
}
.diff-view .add {
  color: #8ee08e;
}
.diff-view .del {
  color: #ff9b9b;
}
.diff-view .meta {
  color: #8ab4f8;
}
.empty-hint {
  padding: 24px;
}
.ops-section {
  margin-top: 18px;
}
.section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 8px;
}
.section-title {
  font-weight: 600;
  font-size: 13px;
}
.tiny {
  font-size: 11px;
}
.small {
  font-size: 12px;
}
.muted {
  color: var(--ngp-muted);
}
.op-detail {
  margin: 0;
  padding: 8px 12px;
  max-height: 200px;
  overflow: auto;
  font-size: 11.5px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>