<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2 class="page-title">{{ t('dashboard.title') }}</h2>
        <p class="page-sub">{{ t('dashboard.subtitle') }}</p>
      </div>
      <div class="row">
        <el-button :icon="Refresh" :loading="loading" @click="load()">{{ t('common.refresh') }}</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('dashboard.add') }}</el-button>
      </div>
    </div>

    <div v-if="loading" class="panel empty-hint">{{ t('dashboard.loading') }}</div>
    <div v-else-if="!instances.length" class="panel empty-hint empty-state">
      <img class="empty-logo" src="/favicon.svg" alt="logo" />
      <p class="empty-title">{{ t('dashboard.emptyTitle') }}</p>
      <p class="muted">{{ t('dashboard.emptyHint') }}</p>
      <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('dashboard.addFirst') }}</el-button>
    </div>

    <div v-else class="grid">
      <div v-for="inst in instances" :key="inst.id" class="card panel">
        <div class="card-top">
          <div class="card-ident">
            <span class="status-dot" :class="{ on: inst.status?.running }"></span>
            <div class="card-heading">
              <div class="card-name" @click="open(inst)">{{ inst.name }}</div>
              <div class="card-path mono" :title="inst.prefix">{{ inst.prefix }}</div>
            </div>
          </div>
          <el-tag :type="inst.status?.running ? 'success' : 'info'" size="small" effect="light">
            {{ inst.status?.running ? t('dashboard.runningWithPid', { pid: inst.status.pid }) : t('dashboard.stopped') }}
          </el-tag>
        </div>
        <div class="card-meta">
          <span class="meta-item">
            <el-icon><Cpu /></el-icon>
            {{ inst.run_mode === 'systemd' ? `systemd: ${inst.systemd_unit || 'nginx'}` : t('dashboard.localProcess') }}
          </span>
          <span class="meta-item">
            <el-icon><Document /></el-icon>
            <span class="mono">{{ inst.conf_path }}</span>
          </span>
        </div>
        <div class="card-actions">
          <el-button size="small" type="primary" plain @click="open(inst)">{{ t('dashboard.manage') }}</el-button>
          <el-button
            v-if="!inst.status?.running"
            size="small"
            :loading="busy[inst.id] === 'start'"
            @click="operate(inst, 'start')"
            >{{ t('ops.start') }}</el-button
          >
          <template v-else>
            <el-button size="small" :loading="busy[inst.id] === 'reload'" @click="operate(inst, 'reload')"
              >{{ t('ops.reload') }}</el-button
            >
            <el-button size="small" :loading="busy[inst.id] === 'stop'" @click="operate(inst, 'stop')"
              >{{ t('ops.stop') }}</el-button
            >
          </template>
          <el-button size="small" :loading="busy[inst.id] === 'test'" @click="operate(inst, 'test')"
            >{{ t('ops.test') }}</el-button
          >
          <el-dropdown trigger="click" @command="(cmd) => onCommand(cmd, inst)">
            <el-button size="small" :icon="MoreFilled" />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">{{ t('dashboard.edit') }}</el-dropdown-item>
                <el-dropdown-item command="restart">{{ t('dashboard.restart') }}</el-dropdown-item>
                <el-dropdown-item command="delete" divided>{{ t('dashboard.delete') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialog" :title="form.id ? t('dashboard.edit') : t('dashboard.addTitle')" width="560px">
      <el-form :model="form" :label-width="locale === 'en' ? '130px' : '110px'">
        <el-form-item :label="t('dashboard.name')">
          <el-input v-model="form.name" :placeholder="t('dashboard.namePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('dashboard.prefixLabel')">
          <div class="path-row">
            <PathInput
              v-model="form.prefix"
              mode="folder"
              :placeholder="t('dashboard.prefixPlaceholder')"
              :title="t('dashboard.prefixTitle')"
            />
            <el-button :loading="detecting" @click="detect">{{ t('dashboard.detect') }}</el-button>
          </div>
        </el-form-item>
        <el-form-item :label="t('dashboard.binaryLabel')">
          <PathInput
            v-model="form.binary"
            mode="file"
            :placeholder="t('dashboard.binaryPlaceholder')"
            :title="t('dashboard.binaryTitle')"
          />
        </el-form-item>
        <el-form-item :label="t('dashboard.confLabel')">
          <PathInput
            v-model="form.conf_path"
            mode="file"
            :placeholder="t('dashboard.confPlaceholder')"
            :title="t('dashboard.confTitle')"
          />
        </el-form-item>
        <el-form-item :label="t('dashboard.runMode')">
          <el-radio-group v-model="form.run_mode">
            <el-radio value="local">{{ t('dashboard.runLocal') }}</el-radio>
            <el-radio value="systemd">{{ t('dashboard.runSystemd') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.run_mode === 'systemd'" :label="t('dashboard.serviceName')">
          <el-input v-model="form.systemd_unit" placeholder="nginx" />
        </el-form-item>
      </el-form>
      <div v-if="candidates.length" class="candidates">
        <div class="muted">{{ t('dashboard.detected') }}</div>
        <div v-for="c in candidates" :key="c.binary" class="candidate" @click="applyCandidate(c)">
          <span class="mono">{{ c.prefix }}</span>
          <el-tag size="small" type="success" effect="plain">{{ c.binary }}</el-tag>
        </div>
      </div>
      <template #footer>
        <el-button @click="dialog = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="outputDialog" :title="t('dashboard.outputTitle')" width="640px">
      <el-alert
        :type="outputOk ? 'success' : 'error'"
        :closable="false"
        :title="outputOk ? t('dashboard.outputOk') : t('dashboard.outputFail')"
      />
      <pre class="output mono">{{ outputText || t('common.noOutput') }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Cpu, Document, MoreFilled, Plus, Refresh } from '@element-plus/icons-vue'
import PathInput from '../components/PathInput.vue'
import { apiDelete, apiGet, apiPost, apiPut } from '../api'
import { holdLoading } from '../utils/busy'

const router = useRouter()
const { t, locale } = useI18n()
const instances = ref([])
const loading = ref(true)
const busy = reactive({})
const dialog = ref(false)
const saving = ref(false)
const detecting = ref(false)
const candidates = ref([])
const outputDialog = ref(false)
const outputText = ref('')
const outputOk = ref(true)

const emptyForm = () => ({
  id: null,
  name: '',
  prefix: '',
  binary: 'nginx',
  conf_path: 'conf/nginx.conf',
  run_mode: 'local',
  systemd_unit: ''
})
const form = reactive(emptyForm())

let timer = null

async function load(silent = false) {
  const started = Date.now()
  if (!silent) loading.value = true
  try {
    instances.value = await apiGet('/instances', { quiet: silent })
  } catch (e) {
    /* 已提示 */
  } finally {
    if (!silent) await holdLoading(started)
    loading.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(() => load(true), 8000)
})
onBeforeUnmount(() => clearInterval(timer))

function open(inst) {
  router.push(`/instances/${inst.id}`)
}

function openCreate() {
  Object.assign(form, emptyForm())
  candidates.value = []
  dialog.value = true
}

function openEdit(inst) {
  Object.assign(form, {
    id: inst.id,
    name: inst.name,
    prefix: inst.prefix,
    binary: inst.binary,
    conf_path: inst.conf_path,
    run_mode: inst.run_mode,
    systemd_unit: inst.systemd_unit
  })
  candidates.value = []
  dialog.value = true
}

async function detect() {
  const started = Date.now()
  detecting.value = true
  try {
    const data = await apiGet('/instances/system/detect')
    candidates.value = data.candidates || []
    if (!candidates.value.length) ElMessage.info(t('dashboard.noCandidates'))
  } catch (e) {
    /* 已提示 */
  } finally {
    await holdLoading(started)
    detecting.value = false
  }
}

function applyCandidate(c) {
  form.prefix = c.prefix
  form.binary = c.binary
  form.conf_path = c.conf_path
  if (!form.name) form.name = t('dashboard.defaultName')
}

async function save() {
  if (!form.name || !form.prefix || !form.binary) {
    ElMessage.warning(t('dashboard.required'))
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      prefix: form.prefix,
      binary: form.binary,
      conf_path: form.conf_path,
      run_mode: form.run_mode,
      systemd_unit: form.systemd_unit
    }
    if (form.id) await apiPut(`/instances/${form.id}`, payload)
    else await apiPost('/instances', payload)
    ElMessage.success(t('dashboard.saved'))
    dialog.value = false
    await load(true)
  } catch (e) {
    /* 已提示 */
  } finally {
    saving.value = false
  }
}

async function operate(inst, action) {
  busy[inst.id] = action
  try {
    const res = await apiPost(`/instances/${inst.id}/ops/${action}`, undefined, { quiet: true })
    outputOk.value = res.ok
    outputText.value = res.output || ''
    if (!res.ok) outputDialog.value = true
    else ElMessage.success(t('ops.success', { action: label(action) }))
    await load(true)
  } catch (e) {
    outputOk.value = false
    outputText.value = e.message
    outputDialog.value = true
  } finally {
    busy[inst.id] = null
  }
}

function label(action) {
  return t(`ops.${action}`)
}

async function onCommand(cmd, inst) {
  if (cmd === 'edit') openEdit(inst)
  if (cmd === 'restart') operate(inst, 'restart')
  if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(
        t('dashboard.deleteConfirm', { name: inst.name }),
        t('dashboard.deleteTitle'),
        { type: 'warning' }
      )
      await apiDelete(`/instances/${inst.id}`)
      ElMessage.success(t('dashboard.deleted'))
      await load(true)
    } catch (e) {
      /* 取消或已提示 */
    }
  }
}
</script>

<style scoped>
.grid {
  display: grid;
  /* 单卡最大 460px：卡片少时不会铺满整行，配合 justify-content 保持居中 */
  grid-template-columns: repeat(auto-fit, minmax(370px, 460px));
  justify-content: center;
  gap: 16px;
}
.card {
  padding: 18px 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
  overflow: hidden;
}
.card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, var(--ngp-brand), transparent 70%);
  opacity: 0;
  transition: opacity 0.25s ease;
}
.card:hover {
  border-color: color-mix(in srgb, var(--ngp-brand) 40%, var(--ngp-border));
  box-shadow: var(--ngp-shadow-md);
  transform: translateY(-2px);
}
.card:hover::before {
  opacity: 1;
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.card-ident {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}
.status-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--ngp-muted);
  flex: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--ngp-muted) 18%, transparent);
}
.status-dot.on {
  background: var(--ngp-brand);
  box-shadow: 0 0 0 3px var(--ngp-brand-soft);
}
.card-heading {
  min-width: 0;
}
.card-name {
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  letter-spacing: -0.1px;
  transition: color 0.2s ease;
}
.card-name:hover {
  color: var(--ngp-brand);
}
.card-path {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ngp-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  font-size: 12px;
  color: var(--ngp-text-2);
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border-soft);
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}
.meta-item .mono {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 2px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 64px 24px;
}
.empty-logo {
  width: 54px;
  height: 54px;
  border-radius: 15px;
  opacity: 0.9;
  box-shadow: var(--ngp-shadow-md);
}
.empty-title {
  margin: 8px 0 0;
  font-size: 16px;
  font-weight: 600;
}
.candidates {
  border-top: 1px dashed var(--ngp-border);
  margin-top: 8px;
  padding-top: 10px;
  font-size: 13px;
}
.path-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.path-row :deep(.el-input) {
  flex: 1;
}
.candidate {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}
.candidate:hover {
  background: var(--ngp-surface-3);
}
</style>