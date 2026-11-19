<template>
  <div class="instance-page">
    <div class="head">
      <div class="head-left">
        <el-button text :icon="ArrowLeft" @click="router.push('/')">{{ t('instance.back') }}</el-button>
        <div class="title-block">
          <h2 class="title">{{ instance?.name || t('instance.fallbackTitle') }}</h2>
          <div class="meta muted mono">
            {{ instance?.prefix }} · {{ instance?.conf_path }}
            <span v-if="instance?.run_mode === 'systemd'"> · systemd: {{ instance?.systemd_unit || 'nginx' }}</span>
          </div>
        </div>
        <span class="status-pill" :class="{ on: running }">
          <i class="status-dot" />
          {{ running ? (pid ? t('instance.runningWithPid', { pid }) : t('instance.running')) : t('instance.stopped') }}
        </span>
        <el-tag v-if="confErrors.length" type="warning" size="small" effect="plain">{{ t('instance.confWarnings') }}</el-tag>
      </div>
      <div class="toolbar">
        <el-button v-if="!running" size="small" type="primary" :loading="opsBusy === 'start'" @click="operate('start')"
          >{{ t('ops.start') }}</el-button
        >
        <template v-else>
          <el-button size="small" :loading="opsBusy === 'reload'" @click="operate('reload')">{{ t('ops.reload') }}</el-button>
          <el-button size="small" :loading="opsBusy === 'restart'" @click="operate('restart')">{{ t('ops.restart') }}</el-button>
          <el-button size="small" :loading="opsBusy === 'stop'" @click="operate('stop')">{{ t('ops.stop') }}</el-button>
        </template>
        <el-button size="small" :loading="opsBusy === 'test'" @click="operate('test')">{{ t('ops.test') }}</el-button>
        <el-button size="small" type="primary" plain :icon="Plus" @click="siteDialog = true">{{ t('site.new') }}</el-button>
        <el-button size="small" :icon="Refresh" circle :loading="refreshing" @click="reloadAll" />
      </div>
    </div>

    <el-tabs v-model="tab" class="instance-tabs">
      <el-tab-pane :label="t('instance.tabFiles')" name="files">
        <div class="editor-layout">
          <div class="sidebar panel">
            <FileTree :files="files" :active="activePath" @select="selectFile" />
          </div>
          <div class="editor-area" v-loading="fileLoading">
            <div class="editor-head panel">
              <div class="path mono" :title="activePath">{{ activePath || t('instance.selectFile') }}</div>
              <span v-if="dirty" class="dirty-dot" :title="t('instance.dirtyTitle')"></span>
              <span class="grow"></span>
              <span v-if="activeFile" class="muted small mono">hash {{ (baseHash || '').slice(0, 8) }}</span>
              <el-button size="small" :disabled="!dirty" @click="revert">{{ t('instance.revert') }}</el-button>
              <el-button size="small" :loading="reloadingActive" :disabled="!activeFile" @click="reloadActive">{{ t('instance.reloadActive') }}</el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="!dirty || !editable"
                :loading="saving"
                @click="openSave"
                >{{ t('instance.saveApply') }}</el-button
              >
            </div>
            <el-alert
              v-if="parseError"
              class="parse-alert"
              type="warning"
              :closable="false"
              show-icon
              :title="t('instance.parseHint', { error: parseError })"
            />
            <el-alert
              v-if="!editable && activeFile"
              class="parse-alert"
              type="info"
              :closable="false"
              show-icon
              :title="t('instance.notText')"
            />
            <CodeEditor v-model="content" :readonly="!editable" class="editor" @save="openSave" />
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane :label="t('instance.tabForm')" name="form" lazy>
        <FormPanel :key="formKey" :instance-id="id" @applied="onApplied" />
      </el-tab-pane>

      <el-tab-pane :label="t('instance.tabHistory')" name="history" lazy>
        <HistoryPanel :key="historyKey" :instance-id="id" @restored="onApplied" />
      </el-tab-pane>

      <el-tab-pane :label="t('instance.tabLogs')" name="logs" lazy>
        <LogsPanel :instance-id="id" />
      </el-tab-pane>

      <el-tab-pane :label="t('instance.tabSites')" name="sites" lazy>
        <SitesPanel :key="sitesKey" :instance-id="id" @changed="onApplied" />
      </el-tab-pane>

      <el-tab-pane :label="t('instance.tabCerts')" name="certs" lazy>
        <CertPanel :instance-id="id" />
      </el-tab-pane>

      <el-tab-pane :label="t('instance.tabChecks')" name="checks" lazy>
        <ChecksPanel :key="checksKey" :instance-id="id" />
      </el-tab-pane>

      <el-tab-pane :label="t('instance.tabBackup')" name="backup" lazy>
        <BackupPanel :key="backupKey" :instance-id="id" @applied="onApplied" />
      </el-tab-pane>
    </el-tabs>

    <SiteWizard v-model="siteDialog" :instance-id="id" @created="onSiteCreated" />

    <el-dialog v-model="saveDialog" :title="t('instance.saveTitle')" width="540px">
      <div class="save-tip muted">{{ t('instance.saveTip', { cmd: 'nginx -t' }) }}</div>
      <el-input v-model="saveMessage" type="textarea" :rows="2" :placeholder="t('instance.saveMessagePlaceholder')" />
      <el-checkbox v-model="doReload" class="save-reload">{{ t('instance.saveReload') }}</el-checkbox>
      <template #footer>
        <el-button @click="saveDialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('instance.saveApply') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="errorDialog" :title="errorTitle" width="720px">
      <el-alert type="error" :closable="false" :title="errorMessage" />
      <el-table v-if="errorErrors.length" :data="errorErrors" size="small" class="err-table">
        <el-table-column prop="level" :label="t('instance.level')" width="80" />
        <el-table-column prop="message" :label="t('instance.info')" min-width="220" />
        <el-table-column prop="file" :label="t('instance.file')" width="200" show-overflow-tooltip />
        <el-table-column prop="line" :label="t('instance.line')" width="70" />
      </el-table>
      <div v-if="errorConflicts.length" class="conflicts">
        <div class="muted">{{ t('instance.conflictHint') }}</div>
        <div v-for="c in errorConflicts" :key="c.path" class="mono conflict-item">{{ c.path }}</div>
      </div>
      <pre v-if="errorOutput" class="output mono">{{ errorOutput }}</pre>
      <template #footer>
        <el-button v-if="errorConflicts.length" :loading="refreshing" @click="reloadAll">{{ t('instance.reloadFiles') }}</el-button>
        <el-button type="primary" @click="errorDialog = false">{{ t('instance.gotIt') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus, Refresh } from '@element-plus/icons-vue'
import { apiGet, apiPost, apiPut } from '../api'
import { holdLoading } from '../utils/busy'
import BackupPanel from '../components/BackupPanel.vue'
import CertPanel from '../components/CertPanel.vue'
import ChecksPanel from '../components/ChecksPanel.vue'
import CodeEditor from '../components/CodeEditor.vue'
import FileTree from '../components/FileTree.vue'
import FormPanel from '../components/FormPanel.vue'
import HistoryPanel from '../components/HistoryPanel.vue'
import LogsPanel from '../components/LogsPanel.vue'
import SiteWizard from '../components/SiteWizard.vue'
import SitesPanel from '../components/SitesPanel.vue'

const props = defineProps({
  id: { type: [String, Number], required: true }
})
const id = computed(() => props.id)
const router = useRouter()
const { t } = useI18n()

const instance = ref(null)
const tab = ref('files')
const files = ref([])
const activeFile = ref(null)
const content = ref('')
const originalContent = ref('')
// 原文件换行符：编辑器会把 CRLF 统一成 LF，保存时按原样写回，避免误判为已修改
const fileEol = ref('\n')
const baseHash = ref('')
const parseError = ref('')
const saving = ref(false)
const refreshing = ref(false)
const reloadingActive = ref(false)
const fileLoading = ref(false)
const opsBusy = ref('')
const formKey = ref(0)
const historyKey = ref(0)
const sitesKey = ref(0)
const checksKey = ref(0)
const backupKey = ref(0)
const siteDialog = ref(false)

const saveDialog = ref(false)
const saveMessage = ref('')
const doReload = ref(true)

const errorDialog = ref(false)
const errorTitle = ref('')
const errorMessage = ref('')
const errorOutput = ref('')
const errorErrors = ref([])
const errorConflicts = ref([])

let statusTimer = null

const running = computed(() => !!instance.value?.status?.running)
const pid = computed(() => instance.value?.status?.pid)
const confErrors = computed(() => instance.value?.status?.conf_errors || [])
const activePath = computed(() => activeFile.value?.path || '')
const editable = computed(() => !!activeFile.value?.editable)
const dirty = computed(() => !!activeFile.value && content.value !== originalContent.value)

function triggerLabel(stage) {
  return (
    {
      test: t('instance.stageTest'),
      reload: t('instance.stageReload'),
      health: t('instance.stageHealth')
    }[stage] || t('instance.errorTitle')
  )
}

async function loadInstance() {
  try {
    instance.value = await apiGet(`/instances/${id.value}`)
  } catch (e) {
    router.push('/')
  }
}

async function loadStatus() {
  try {
    const status = await apiGet(`/instances/${id.value}/status`, { quiet: true })
    if (instance.value) instance.value.status = status
  } catch (e) {
    /* 忽略轮询错误 */
  }
}

async function loadTree() {
  try {
    const res = await apiGet(`/instances/${id.value}/tree`)
    files.value = res.files || []
    const target = files.value.find((f) => f.is_main) || files.value.find((f) => f.included)
    if (!activeFile.value && target) {
      activeFile.value = target
      await loadFile(target)
    }
  } catch (e) {
    /* 已提示 */
  }
}

async function loadFile(file) {
  try {
    const res = await apiGet(`/instances/${id.value}/file?path=${encodeURIComponent(file.path)}`)
    activeFile.value = { ...file, ...res }
    const raw = res.content || ''
    fileEol.value = raw.includes('\r\n') ? '\r\n' : '\n'
    content.value = raw.replace(/\r\n/g, '\n')
    originalContent.value = content.value
    baseHash.value = res.hash
    parseError.value = res.parse_error || ''
  } catch (e) {
    activeFile.value = null
    content.value = ''
    originalContent.value = ''
  }
}

async function selectFile(file) {
  if (file.path === activePath.value) return
  if (dirty.value) {
    try {
      await ElMessageBox.confirm(t('instance.unsavedConfirm'), t('instance.unsavedTitle'), {
        type: 'warning',
        confirmButtonText: t('instance.discard'),
        cancelButtonText: t('common.cancel')
      })
    } catch (e) {
      return
    }
  }
  activeFile.value = file
  const started = Date.now()
  fileLoading.value = true
  try {
    await loadFile(file)
  } finally {
    await holdLoading(started)
    fileLoading.value = false
  }
}

function revert() {
  content.value = originalContent.value
}

async function reloadActive() {
  if (!activeFile.value) return
  if (dirty.value) {
    try {
      await ElMessageBox.confirm(t('instance.reloadConfirm'), t('instance.reloadTitle'), { type: 'warning' })
    } catch (e) {
      return
    }
  }
  reloadingActive.value = true
  const started = Date.now()
  try {
    await loadFile(activeFile.value)
    ElMessage.success(t('instance.reloaded'))
  } finally {
    await holdLoading(started)
    reloadingActive.value = false
  }
}

function openSave() {
  if (!dirty.value) {
    ElMessage.info(t('instance.noChanges'))
    return
  }
  if (!editable.value) {
    ElMessage.warning(t('instance.notEditable'))
    return
  }
  if (!saveMessage.value) {
    saveMessage.value = t('instance.manualMessage', {
      file: activeFile.value?.rel || activeFile.value?.name || ''
    })
  }
  saveDialog.value = true
}

async function save() {
  if (!activeFile.value) return
  saving.value = true
  try {
    await apiPut(`/instances/${id.value}/file`, {
      path: activePath.value,
      content: fileEol.value === '\r\n' ? content.value.replace(/\n/g, '\r\n') : content.value,
      base_hash: baseHash.value,
      message: saveMessage.value || t('instance.editMessage'),
      reload: doReload.value
    })
    saveDialog.value = false
    ElMessage.success(doReload.value ? t('instance.savedReloaded') : t('instance.saved'))
    await afterApply()
  } catch (e) {
    saveDialog.value = false
    showError(e)
  } finally {
    saving.value = false
  }
}

async function afterApply() {
  formKey.value += 1
  historyKey.value += 1
  sitesKey.value += 1
  checksKey.value += 1
  backupKey.value += 1
  await Promise.all([loadStatus(), loadTree()])
  if (activeFile.value) await loadFile(activeFile.value)
}

function showError(e) {
  const detail = e.detail || {}
  errorTitle.value = triggerLabel(detail.stage)
  errorMessage.value = e.message || t('instance.errorTitle')
  errorOutput.value = detail.output || ''
  errorErrors.value = detail.errors || []
  errorConflicts.value = detail.conflicts || []
  errorDialog.value = true
}

function onApplied() {
  afterApply()
}

async function onSiteCreated() {
  tab.value = 'files'
  await afterApply()
}

async function reloadAll() {
  const started = Date.now()
  refreshing.value = true
  try {
    errorDialog.value = false
    await loadInstance()
    await loadTree()
    if (activeFile.value) await loadFile(activeFile.value)
  } finally {
    await holdLoading(started)
    refreshing.value = false
  }
}

function opLabel(action) {
  return t(`ops.${action}`)
}

async function operate(action) {
  opsBusy.value = action
  try {
    const res = await apiPost(`/instances/${id.value}/ops/${action}`, undefined, { quiet: true })
    if (!res.ok) {
      errorTitle.value = t('ops.fail', { action: opLabel(action) })
      errorMessage.value = t('instance.opFailMsg')
      errorOutput.value = res.output || ''
      errorErrors.value = []
      errorConflicts.value = []
      errorDialog.value = true
    } else {
      ElMessage.success(t('ops.success', { action: opLabel(action) }))
    }
    await loadStatus()
  } catch (e) {
    showError(e)
  } finally {
    opsBusy.value = ''
  }
}

onMounted(async () => {
  await loadInstance()
  await loadTree()
  statusTimer = setInterval(loadStatus, 10000)
})

onBeforeUnmount(() => clearInterval(statusTimer))
</script>

<style scoped>
.instance-page {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 20px 26px 26px;
  /* 整页高度固定，滚动交给标签内容区，切换标签时页面宽度/位置都不再变化 */
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.head {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.title-block {
  min-width: 0;
}
.title {
  margin: 0;
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meta {
  font-size: 11.5px;
  margin-top: 3px;
  word-break: break-all;
  opacity: 0.9;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  color: var(--ngp-muted);
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border);
  flex: none;
}
.status-pill .status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ngp-muted);
}
.status-pill.on {
  color: var(--ngp-brand-strong);
  background: var(--ngp-brand-soft);
  border-color: color-mix(in srgb, var(--ngp-brand) 35%, transparent);
}
.status-pill.on .status-dot {
  background: var(--ngp-brand);
  box-shadow: 0 0 0 3px var(--ngp-brand-soft);
}
.instance-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.instance-tabs :deep(.el-tabs__header) {
  flex: none;
  margin-bottom: 14px;
}
.instance-tabs :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  /* 始终预留滚动条宽度，避免某些标签页出现滚动条时内容宽度跳动 */
  scrollbar-gutter: stable;
}
.instance-tabs :deep(.el-tab-pane) {
  height: 100%;
}
.instance-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--ngp-border);
}
.instance-tabs :deep(.el-tabs__item) {
  height: 36px;
  padding: 0 16px;
  border-radius: 9px;
  color: var(--ngp-text-2);
  transition: color 0.2s ease, background-color 0.2s ease;
}
/* Element Plus 会去掉首个/末尾标签的左右内边距，导致文字贴边、选中底色被裁切 */
.instance-tabs :deep(.el-tabs__header .el-tabs__item:nth-child(2)) {
  padding-left: 16px;
}
.instance-tabs :deep(.el-tabs__header .el-tabs__item:last-child) {
  padding-right: 16px;
}
.instance-tabs :deep(.el-tabs__item:hover) {
  color: var(--ngp-brand);
}
.instance-tabs :deep(.el-tabs__item.is-active) {
  color: var(--ngp-brand-strong);
  background: var(--ngp-brand-soft);
}
.instance-tabs :deep(.el-tabs__active-bar) {
  display: none;
}
.editor-layout {
  display: flex;
  gap: 12px;
  height: 100%;
  min-height: 0;
}
.sidebar {
  width: 282px;
  flex: none;
  overflow: hidden;
}
.editor-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.editor-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  flex-wrap: wrap;
  background: var(--ngp-surface);
}
.path {
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
  padding: 3px 9px;
  border-radius: 7px;
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border-soft);
  color: var(--ngp-text-2);
}
.small {
  font-size: 12px;
}
.dirty-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-warning);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--el-color-warning) 22%, transparent);
  flex: none;
}
.editor {
  flex: 1;
  min-height: 0;
}
.parse-alert {
  padding: 6px 10px;
}
.save-tip {
  font-size: 13px;
  margin-bottom: 10px;
}
.save-reload {
  margin-top: 10px;
}
.err-table {
  margin-top: 10px;
}
.conflicts {
  margin-top: 10px;
  font-size: 13px;
}
.conflict-item {
  padding: 4px 0;
  word-break: break-all;
}
.output {
  margin-top: 10px;
}
</style>