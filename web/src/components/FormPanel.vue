<template>
  <div v-loading="loading" class="form-panel">
    <div class="toolbar sticky">
      <el-button :icon="Refresh" :loading="loading" @click="load">{{ t('common.refresh') }}</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canSave" @click="save">{{ t('form.save') }}</el-button>
      <el-checkbox v-model="doReload" size="small">{{ t('form.saveReload') }}</el-checkbox>
      <span class="muted hint">{{ t('form.tip') }}</span>
    </div>

    <el-alert
      v-if="data && data.readonly"
      type="warning"
      :closable="false"
      show-icon
      :title="data.reason || t('form.readonly')"
      class="readonly-alert"
    />

    <template v-if="data && !data.readonly">
      <div class="section-title">{{ t('form.serverSection') }}</div>
      <div v-if="!servers.length" class="empty-hint panel">{{ t('form.noServer') }}</div>
      <div v-for="server in servers" :key="server.id" class="block-card panel">
        <div class="block-head" @click="server.open = !server.open">
          <el-icon class="chevron" :class="{ open: server.open }"><CaretRight /></el-icon>
          <span class="mono strong">server</span>
          <span class="muted mono">{{ server.file }}:{{ server.line }}</span>
          <el-tag v-if="server.unknown?.length" size="small" type="info" :title="server.unknown.join(', ')">
            {{ t('form.unknown', { n: server.unknown.length }) }}
          </el-tag>
          <span class="grow"></span>
          <el-tag v-if="server.fields.listen" size="small" effect="plain">
            {{ server.fields.listen.items.map((i) => i.draft).join(' / ') || t('form.notListening') }}
          </el-tag>
        </div>

        <div v-show="server.open" class="block-body">
          <div class="field-grid">
            <template v-for="(group, name) in server.fields" :key="name">
              <div class="field-label">
                <div class="mono">{{ name }}</div>
                <div v-if="hint(name, 'server')" class="field-hint">{{ hint(name, 'server') }}</div>
              </div>
              <div class="field-values">
                <div v-for="item in group.items" :key="item.key" class="value-row">
                  <el-input
                    v-model="item.draft"
                    size="small"
                    :placeholder="group.multi ? t('form.emptyMulti') : ''"
                  />
                  <el-button
                    v-if="pickMode(name, 'server')"
                    text
                    size="small"
                    :icon="FolderOpened"
                    :title="pickMode(name, 'server') === 'folder' ? t('form.pickFolder') : t('form.pickFile')"
                    @click="pickPath(item, pickMode(name, 'server'))"
                  />
                  <el-button
                    v-if="group.multi"
                    text
                    size="small"
                    :icon="Delete"
                    @click="removeItem(group, item)"
                  />
                </div>
                <div v-if="!group.items.length" class="muted small">{{ t('form.emptyValue') }}</div>
              </div>
            </template>
          </div>

          <div class="add-row">
            <el-select
              v-model="server.addName"
              size="small"
              :placeholder="t('form.addDirective')"
              style="width: 200px"
              popper-class="ngp-field-popper"
            >
              <el-option v-for="opt in assignable(server)" :key="opt" :label="opt" :value="opt">
                <span class="opt-name mono">{{ opt }}</span>
                <span v-if="hint(opt, 'server')" class="opt-hint">{{ hint(opt, 'server') }}</span>
              </el-option>
            </el-select>
            <el-button size="small" :disabled="!server.addName" @click="addField(server)">{{ t('form.addField') }}</el-button>
          </div>

          <div v-if="server.locations.length" class="locations">
            <div class="section-title small-title">{{ t('form.locationSection') }}</div>
            <div v-for="loc in server.locations" :key="loc.id" class="block-card nested panel">
              <div class="block-head" @click="loc.open = !loc.open">
                <el-icon class="chevron" :class="{ open: loc.open }"><CaretRight /></el-icon>
                <span class="mono strong">location</span>
                <span class="mono">{{ loc.args.join(' ') }}</span>
                <el-tag v-if="loc.unknown?.length" size="small" type="info" :title="loc.unknown.join(', ')">
                  {{ t('form.unknown', { n: loc.unknown.length }) }}
                </el-tag>
                <span class="grow"></span>
                <span class="muted small mono">{{ loc.file }}:{{ loc.line }}</span>
              </div>
              <div v-show="loc.open" class="block-body">
                <div class="field-grid">
                  <template v-for="(group, name) in loc.fields" :key="name">
                    <div class="field-label">
                      <div class="mono">{{ name }}</div>
                      <div v-if="hint(name, 'location')" class="field-hint">{{ hint(name, 'location') }}</div>
                    </div>
                    <div class="field-values">
                      <div v-for="item in group.items" :key="item.key" class="value-row">
                        <el-input
                          v-model="item.draft"
                          size="small"
                          :placeholder="group.multi ? t('form.emptyMulti') : ''"
                        />
                        <el-button
                          v-if="pickMode(name, 'location')"
                          text
                          size="small"
                          :icon="FolderOpened"
                          :title="pickMode(name, 'location') === 'folder' ? t('form.pickFolder') : t('form.pickFile')"
                          @click="pickPath(item, pickMode(name, 'location'))"
                        />
                        <el-button
                          v-if="group.multi"
                          text
                          size="small"
                          :icon="Delete"
                          @click="removeItem(group, item)"
                        />
                      </div>
                      <div v-if="!group.items.length" class="muted small">{{ t('form.emptyValue') }}</div>
                    </div>
                  </template>
                </div>
                <div class="add-row">
                  <el-select
                    v-model="loc.addName"
                    size="small"
                    :placeholder="t('form.addDirective')"
                    style="width: 200px"
                    popper-class="ngp-field-popper"
                  >
                    <el-option v-for="opt in assignable(loc)" :key="opt" :label="opt" :value="opt">
                      <span class="opt-name mono">{{ opt }}</span>
                      <span v-if="hint(opt, 'location')" class="opt-hint">{{ hint(opt, 'location') }}</span>
                    </el-option>
                  </el-select>
                  <el-button size="small" :disabled="!loc.addName" @click="addField(loc)">{{ t('form.addField') }}</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="section-title">{{ t('form.upstreamSection') }}</div>
      <div v-if="!upstreams.length" class="empty-hint panel">{{ t('form.noUpstream') }}</div>
      <div v-for="up in upstreams" :key="up.id" class="block-card panel">
        <div class="block-head" @click="up.open = !up.open">
          <el-icon class="chevron" :class="{ open: up.open }"><CaretRight /></el-icon>
          <span class="mono strong">upstream</span>
          <span class="mono">{{ up.name }}</span>
          <el-tag v-if="up.unknown?.length" size="small" type="info" :title="up.unknown.join(', ')">
            {{ t('form.unknown', { n: up.unknown.length }) }}
          </el-tag>
          <span class="grow"></span>
          <span class="muted small mono">{{ up.file }}:{{ up.line }}</span>
        </div>
        <div v-show="up.open" class="block-body">
          <div class="field-grid">
            <template v-for="(group, name) in up.fields" :key="name">
              <div class="field-label">
                <div class="mono">{{ name }}</div>
                <div v-if="hint(name, 'upstream')" class="field-hint">{{ hint(name, 'upstream') }}</div>
              </div>
              <div class="field-values">
                <div v-for="item in group.items" :key="item.key" class="value-row">
                  <el-input v-model="item.draft" size="small" />
                  <el-button v-if="group.multi" text size="small" :icon="Delete" @click="removeItem(group, item)" />
                </div>
                <div v-if="!group.items.length" class="muted small">{{ t('form.emptyValue') }}</div>
              </div>
            </template>
          </div>
          <div class="add-row">
            <el-select
              v-model="up.addName"
              size="small"
              :placeholder="t('form.addDirective')"
              style="width: 200px"
              popper-class="ngp-field-popper"
            >
              <el-option v-for="opt in assignable(up)" :key="opt" :label="opt" :value="opt">
                <span class="opt-name mono">{{ opt }}</span>
                <span v-if="hint(opt, 'upstream')" class="opt-hint">{{ hint(opt, 'upstream') }}</span>
              </el-option>
            </el-select>
            <el-button size="small" :disabled="!up.addName" @click="addField(up)">{{ t('form.addField') }}</el-button>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-else-if="!loading && !data" :description="t('form.empty')" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { CaretRight, Delete, FolderOpened, Refresh } from '@element-plus/icons-vue'
import { apiGet, apiPost } from '../api'
import { holdLoading } from '../utils/busy'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const emit = defineEmits(['applied'])
const { t, te } = useI18n()

// 表单字段说明：按块类型区分同名指令的含义，文案在 i18n 的 form.hints 下
function hint(name, scope) {
  const key = `form.hints.${scope}.${name}`
  return te(key) ? t(key) : ''
}

// 需要选择本机路径的指令：folder 为目录选择，file 为文件选择
const PICK_TARGETS = {
  server: { root: 'folder', ssl_certificate: 'file', ssl_certificate_key: 'file' },
  location: { root: 'folder', alias: 'folder' },
  upstream: {}
}

function pickMode(name, scope) {
  return PICK_TARGETS[scope]?.[name] || ''
}

async function pickPath(item, mode) {
  try {
    const res = await apiPost('/system/pick', {
      mode,
      title: mode === 'folder' ? t('form.pickTitleFolder') : t('form.pickTitleFile'),
      initial: item.draft ? (mode === 'folder' ? item.draft : item.draft.replace(/[\\/][^\\/]*$/, '')) : ''
    })
    if (res?.path) item.draft = res.path
  } catch (e) {
    /* 错误已由全局提示 */
  }
}

const loading = ref(true)
const saving = ref(false)
const doReload = ref(true)
const data = ref(null)
const servers = ref([])
const upstreams = ref([])
let baseline = ''

function splitArgs(text) {
  const out = []
  let cur = ''
  let quote = null
  let has = false
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i]
    if (quote) {
      if (ch === '\\' && i + 1 < text.length) {
        cur += ch + text[i + 1]
        i += 1
        continue
      }
      if (ch === quote) {
        quote = null
        continue
      }
      cur += ch
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      has = true
      continue
    }
    if (/\s/.test(ch)) {
      if (cur || has) {
        out.push(cur)
        cur = ''
        has = false
      }
      continue
    }
    cur += ch
  }
  if (cur || has) out.push(cur)
  return out
}

let keySeq = 0
function makeItem(entry) {
  keySeq += 1
  return {
    key: `f${keySeq}`,
    file: entry?.file || null,
    start: entry?.start ?? null,
    line: entry?.line || 0,
    args: entry?.args ? [...entry.args] : [],
    draft: entry?.args ? entry.args.join(' ') : '',
    removed: false
  }
}

function buildFields(defs, multiNames, source) {
  const fields = {}
  for (const name of defs) {
    const entries = source?.[name] || []
    fields[name] = {
      multi: multiNames.includes(name),
      items: entries.map((entry) => makeItem(entry))
    }
  }
  return fields
}

function buildServer(raw) {
  const fields = buildFields(data.value.fields.server, data.value.fields.server_multi, raw.fields)
  return {
    id: raw.id,
    file: raw.file,
    start: raw.start,
    line: raw.line,
    unknown: raw.unknown || [],
    open: false,
    addName: '',
    fields,
    locations: (raw.locations || []).map((loc) => {
      const locFields = buildFields(data.value.fields.location, data.value.fields.location_multi, loc.fields)
      return {
        id: loc.id,
        file: loc.file,
        start: loc.start,
        line: loc.line,
        args: [...loc.args],
        unknown: loc.unknown || [],
        open: false,
        addName: '',
        fields: locFields
      }
    })
  }
}

function buildUpstream(raw) {
  const fields = buildFields(data.value.fields.upstream, ['server'], raw.fields)
  return {
    id: raw.id,
    file: raw.file,
    start: raw.start,
    line: raw.line,
    name: raw.name,
    unknown: raw.unknown || [],
    open: false,
    addName: '',
    fields
  }
}

const snapshot = computed(() => JSON.stringify({ servers: servers.value, upstreams: upstreams.value }))
const dirty = computed(() => snapshot.value !== baseline)
const canSave = computed(() => !!data.value && !data.value.readonly && dirty.value)

async function load() {
  const started = Date.now()
  loading.value = true
  try {
    const result = await apiGet(`/instances/${props.instanceId}/form`)
    data.value = result
    servers.value = (result.servers || []).map(buildServer)
    upstreams.value = (result.upstreams || []).map(buildUpstream)
    if (servers.value.length) servers.value[0].open = true
    if (upstreams.value.length) upstreams.value[0].open = true
    baseline = snapshot.value
  } catch (e) {
    /* 已提示 */
  } finally {
    await holdLoading(started)
    loading.value = false
  }
}

onMounted(load)

function assignable(block) {
  return Object.keys(block.fields).filter((name) => {
    const group = block.fields[name]
    return group.multi || !group.items.some((item) => item.start != null || item.draft)
  })
}

function addField(block) {
  const name = block.addName
  if (!name) return
  block.fields[name].items.push(makeItem(null))
  block.addName = ''
}

function removeItem(group, item) {
  const idx = group.items.indexOf(item)
  if (idx >= 0) group.items.splice(idx, 1)
}

function collectBlock(block, edits, inserts) {
  for (const [name, group] of Object.entries(block.fields)) {
    for (const item of group.items) {
      if (item.removed) continue
      const args = splitArgs(item.draft || '')
      if (!group.multi && item.start != null && !args.length && item.args.length) {
        throw new Error(t('form.requiredValue', { name }))
      }
      if (item.start == null) {
        if (args.length) {
          inserts.push({ file: block.file, parent_start: block.start, name, args })
        }
      } else if (args.join('\u0000') !== item.args.join('\u0000')) {
        edits.push({ file: item.file, start: item.start, args })
      }
    }
  }
}

async function save() {
  const edits = []
  const inserts = []
  try {
    for (const server of servers.value) {
      collectBlock(server, edits, inserts)
      for (const loc of server.locations) collectBlock(loc, edits, inserts)
    }
    for (const up of upstreams.value) collectBlock(up, edits, inserts)
  } catch (e) {
    ElMessage.warning(e.message)
    return
  }
  if (!edits.length && !inserts.length) {
    ElMessage.info(t('form.noChanges'))
    return
  }
  saving.value = true
  try {
    const res = await apiPost(`/instances/${props.instanceId}/form`, {
      edits,
      inserts,
      message: t('form.message'),
      reload: doReload.value
    })
    ElMessage.success(res.reloaded ? t('form.savedReloaded') : t('form.saved'))
    emit('applied', res)
    await load()
  } catch (e) {
    /* 错误已由全局提示，这里保持页面状态 */
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.form-panel {
  min-height: 200px;
}
.toolbar.sticky {
  position: sticky;
  top: 0;
  z-index: 5;
  padding: 4px 0 12px;
  background: var(--ngp-bg);
}
.hint {
  font-size: 12.5px;
}
.readonly-alert {
  margin-bottom: 12px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 6px 0 10px;
}
.section-title.small-title {
  font-size: 13px;
  margin-top: 14px;
}
.block-card {
  margin-bottom: 12px;
  overflow: hidden;
}
.block-card.nested {
  margin-bottom: 10px;
  background: var(--ngp-surface-2);
}
.block-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}
.block-head:hover {
  background: var(--ngp-surface-3);
}
.chevron {
  transition: transform 0.15s ease;
  color: var(--ngp-muted);
}
.chevron.open {
  transform: rotate(90deg);
}
.strong {
  font-weight: 600;
}
.block-body {
  padding: 4px 14px 14px;
  border-top: 1px solid var(--ngp-border);
}
.field-grid {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 6px 12px;
  align-items: start;
  padding-top: 10px;
}
.field-label {
  font-size: 12.5px;
  color: var(--ngp-text-2);
  padding-top: 5px;
  word-break: break-all;
}
.field-hint {
  margin-top: 2px;
  font-size: 11.5px;
  line-height: 1.35;
  color: var(--ngp-muted);
  word-break: normal;
}
.field-values {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.value-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.value-row :deep(.el-input) {
  max-width: 560px;
}
.small {
  font-size: 12px;
}
.add-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--ngp-border);
}
.locations {
  margin-top: 8px;
}
.empty-hint {
  padding: 24px;
}
/* 下拉选项里的指令说明：popper 挂载在 body 上，需要全局样式 */
:global(.ngp-field-popper) {
  min-width: 340px !important;
}
:global(.ngp-field-popper .el-select-dropdown__item) {
  height: auto;
  line-height: 1.4;
  padding-top: 6px;
  padding-bottom: 6px;
}
:global(.ngp-field-popper .opt-name) {
  display: block;
  font-size: 12.5px;
}
:global(.ngp-field-popper .opt-hint) {
  display: block;
  font-size: 11.5px;
  color: var(--ngp-muted);
}
</style>