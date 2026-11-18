<template>
  <div class="instance-page">
    <div class="head">
      <div class="head-left">
        <el-button text :icon="ArrowLeft" @click="router.push('/')">返回</el-button>
        <div class="title-block">
          <h2 class="title">{{ instance?.name || '实例' }}</h2>
          <div class="meta muted mono">
            {{ instance?.prefix }} · {{ instance?.conf_path }}
            <span v-if="instance?.run_mode === 'systemd'"> · systemd: {{ instance?.systemd_unit || 'nginx' }}</span>
          </div>
        </div>
        <span class="status-pill" :class="{ on: running }">
          <i class="status-dot" />
          {{ running ? `运行中${pid ? ' · ' + pid : ''}` : '已停止' }}
        </span>
        <el-tag v-if="confErrors.length" type="warning" size="small" effect="plain">配置有告警</el-tag>
      </div>
      <div class="toolbar">
        <el-button v-if="!running" size="small" type="primary" :loading="opsBusy === 'start'" @click="operate('start')"
          >启动</el-button
        >
        <template v-else>
          <el-button size="small" :loading="opsBusy === 'reload'" @click="operate('reload')">重载</el-button>
          <el-button size="small" :loading="opsBusy === 'restart'" @click="operate('restart')">重启</el-button>
          <el-button size="small" :loading="opsBusy === 'stop'" @click="operate('stop')">停止</el-button>
        </template>
        <el-button size="small" :loading="opsBusy === 'test'" @click="operate('test')">测试配置</el-button>
        <el-button size="small" :icon="Refresh" circle @click="reloadAll" />
      </div>
    </div>

    <el-tabs v-model="tab" class="instance-tabs">
      <el-tab-pane label="文件编辑" name="files">
        <div class="editor-layout">
          <div class="sidebar panel">
            <FileTree :files="files" :active="activePath" @select="selectFile" />
          </div>
          <div class="editor-area">
            <div class="editor-head panel">
              <div class="path mono" :title="activePath">{{ activePath || '请选择左侧配置文件' }}</div>
              <span v-if="dirty" class="dirty-dot" title="有未保存的修改"></span>
              <span class="grow"></span>
              <span v-if="activeFile" class="muted small mono">hash {{ (baseHash || '').slice(0, 8) }}</span>
              <el-button size="small" :disabled="!dirty" @click="revert">撤销修改</el-button>
              <el-button size="small" :disabled="!activeFile" @click="reloadActive">重新载入</el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="!dirty || !editable"
                :loading="saving"
                @click="openSave"
                >保存并应用</el-button
              >
            </div>
            <el-alert
              v-if="parseError"
              class="parse-alert"
              type="warning"
              :closable="false"
              show-icon
              :title="`语法提示：${parseError}`"
            />
            <el-alert
              v-if="!editable && activeFile"
              class="parse-alert"
              type="info"
              :closable="false"
              show-icon
              title="该文件不是文本配置，无法编辑"
            />
            <CodeEditor v-model="content" :readonly="!editable" class="editor" @save="openSave" />
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="结构化表单" name="form" lazy>
        <FormPanel :key="formKey" :instance-id="id" @applied="onApplied" />
      </el-tab-pane>

      <el-tab-pane label="历史记录" name="history" lazy>
        <HistoryPanel :key="historyKey" :instance-id="id" @restored="onApplied" />
      </el-tab-pane>

      <el-tab-pane label="日志" name="logs" lazy>
        <LogsPanel :instance-id="id" />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="saveDialog" title="应用配置修改" width="540px">
      <div class="save-tip muted">
        保存后会写入磁盘并执行 <span class="mono">nginx -t</span> 校验；校验失败会自动还原并保留快照。
      </div>
      <el-input v-model="saveMessage" type="textarea" :rows="2" placeholder="修改说明（会记录到历史中）" />
      <el-checkbox v-model="doReload" class="save-reload">校验通过后重载 nginx（推荐）</el-checkbox>
      <template #footer>
        <el-button @click="saveDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存并应用</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="errorDialog" :title="errorTitle" width="720px">
      <el-alert type="error" :closable="false" :title="errorMessage" />
      <el-table v-if="errorErrors.length" :data="errorErrors" size="small" class="err-table">
        <el-table-column prop="level" label="级别" width="80" />
        <el-table-column prop="message" label="信息" min-width="220" />
        <el-table-column prop="file" label="文件" width="200" show-overflow-tooltip />
        <el-table-column prop="line" label="行" width="70" />
      </el-table>
      <div v-if="errorConflicts.length" class="conflicts">
        <div class="muted">以下文件已在磁盘上被其他程序修改：</div>
        <div v-for="c in errorConflicts" :key="c.path" class="mono conflict-item">{{ c.path }}</div>
      </div>
      <pre v-if="errorOutput" class="output mono">{{ errorOutput }}</pre>
      <template #footer>
        <el-button v-if="errorConflicts.length" @click="reloadAll">重新加载文件</el-button>
        <el-button type="primary" @click="errorDialog = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { apiGet, apiPost, apiPut } from '../api'
import CodeEditor from '../components/CodeEditor.vue'
import FileTree from '../components/FileTree.vue'
import FormPanel from '../components/FormPanel.vue'
import HistoryPanel from '../components/HistoryPanel.vue'
import LogsPanel from '../components/LogsPanel.vue'

const props = defineProps({
  id: { type: [String, Number], required: true }
})
const id = computed(() => props.id)
const router = useRouter()

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
const opsBusy = ref('')
const formKey = ref(0)
const historyKey = ref(0)

const saveDialog = ref(false)
const saveMessage = ref('')
const doReload = ref(true)

const errorDialog = ref(false)
const errorTitle = ref('操作失败')
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
      test: '配置校验失败（已自动还原）',
      reload: '重载失败（已自动回滚）',
      health: '健康检查失败（已自动回滚）'
    }[stage] || '操作失败'
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
      await ElMessageBox.confirm('当前文件有未保存的修改，切换后会丢失，是否继续？', '未保存的修改', {
        type: 'warning',
        confirmButtonText: '放弃修改',
        cancelButtonText: '取消'
      })
    } catch (e) {
      return
    }
  }
  activeFile.value = file
  await loadFile(file)
}

function revert() {
  content.value = originalContent.value
}

async function reloadActive() {
  if (!activeFile.value) return
  if (dirty.value) {
    try {
      await ElMessageBox.confirm('重新载入会丢弃未保存的修改，是否继续？', '重新载入', { type: 'warning' })
    } catch (e) {
      return
    }
  }
  await loadFile(activeFile.value)
  ElMessage.success('已重新载入')
}

function openSave() {
  if (!dirty.value) {
    ElMessage.info('没有需要保存的修改')
    return
  }
  if (!editable.value) {
    ElMessage.warning('该文件不支持编辑')
    return
  }
  if (!saveMessage.value) {
    saveMessage.value = `手动编辑 ${activeFile.value?.rel || activeFile.value?.name || ''}`
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
      message: saveMessage.value || '编辑配置文件',
      reload: doReload.value
    })
    saveDialog.value = false
    ElMessage.success(doReload.value ? '已保存并重载 nginx' : '已保存')
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
  await Promise.all([loadStatus(), loadTree()])
  if (activeFile.value) await loadFile(activeFile.value)
}

function showError(e) {
  const detail = e.detail || {}
  errorTitle.value = triggerLabel(detail.stage)
  errorMessage.value = e.message || '操作失败'
  errorOutput.value = detail.output || ''
  errorErrors.value = detail.errors || []
  errorConflicts.value = detail.conflicts || []
  errorDialog.value = true
}

function onApplied() {
  afterApply()
}

async function reloadAll() {
  errorDialog.value = false
  await loadInstance()
  await loadTree()
  if (activeFile.value) await loadFile(activeFile.value)
}

function opLabel(action) {
  return { start: '启动', stop: '停止', reload: '重载', restart: '重启', test: '配置测试' }[action] || action
}

async function operate(action) {
  opsBusy.value = action
  try {
    const res = await apiPost(`/instances/${id.value}/ops/${action}`, undefined, { quiet: true })
    if (!res.ok) {
      errorTitle.value = `${opLabel(action)}失败`
      errorMessage.value = 'nginx 返回了非零退出码，请查看下方输出'
      errorOutput.value = res.output || ''
      errorErrors.value = []
      errorConflicts.value = []
      errorDialog.value = true
    } else {
      ElMessage.success(`${opLabel(action)}成功`)
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