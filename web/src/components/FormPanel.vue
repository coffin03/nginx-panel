<template>
  <div v-loading="loading" class="form-panel">
    <div class="toolbar sticky">
      <el-button :icon="Refresh" @click="load">刷新</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canSave" @click="save">保存表单修改</el-button>
      <el-checkbox v-model="doReload" size="small">保存后重载 nginx</el-checkbox>
      <span class="muted hint">表单只覆盖常用指令，其余配置请切换到「文件编辑」</span>
    </div>

    <el-alert
      v-if="data && data.readonly"
      type="warning"
      :closable="false"
      show-icon
      :title="data.reason || '当前配置存在语法问题，表单已锁定'"
      class="readonly-alert"
    />

    <template v-if="data && !data.readonly">
      <div class="section-title">server 块</div>
      <div v-if="!servers.length" class="empty-hint panel">没有找到 server 块</div>
      <div v-for="server in servers" :key="server.id" class="block-card panel">
        <div class="block-head" @click="server.open = !server.open">
          <el-icon class="chevron" :class="{ open: server.open }"><CaretRight /></el-icon>
          <span class="mono strong">server</span>
          <span class="muted mono">{{ server.file }}:{{ server.line }}</span>
          <el-tag v-if="server.unknown?.length" size="small" type="info" :title="server.unknown.join('、')">
            {{ server.unknown.length }} 条指令未纳入表单
          </el-tag>
          <span class="grow"></span>
          <el-tag v-if="server.fields.listen" size="small" effect="plain">
            {{ server.fields.listen.items.map((i) => i.draft).join(' / ') || '未监听' }}
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
                    :placeholder="group.multi ? '可留空表示删除' : ''"
                  />
                  <el-button
                    v-if="pickMode(name, 'server')"
                    text
                    size="small"
                    :icon="FolderOpened"
                    :title="pickMode(name, 'server') === 'folder' ? '选择文件夹' : '选择文件'"
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
                <div v-if="!group.items.length" class="muted small">（未设置）</div>
              </div>
            </template>
          </div>

          <div class="add-row">
            <el-select
              v-model="server.addName"
              size="small"
              placeholder="新增指令"
              style="width: 200px"
              popper-class="ngp-field-popper"
            >
              <el-option v-for="opt in assignable(server)" :key="opt" :label="opt" :value="opt">
                <span class="opt-name mono">{{ opt }}</span>
                <span v-if="hint(opt, 'server')" class="opt-hint">{{ hint(opt, 'server') }}</span>
              </el-option>
            </el-select>
            <el-button size="small" :disabled="!server.addName" @click="addField(server)">添加字段</el-button>
          </div>

          <div v-if="server.locations.length" class="locations">
            <div class="section-title small-title">location 块</div>
            <div v-for="loc in server.locations" :key="loc.id" class="block-card nested panel">
              <div class="block-head" @click="loc.open = !loc.open">
                <el-icon class="chevron" :class="{ open: loc.open }"><CaretRight /></el-icon>
                <span class="mono strong">location</span>
                <span class="mono">{{ loc.args.join(' ') }}</span>
                <el-tag v-if="loc.unknown?.length" size="small" type="info" :title="loc.unknown.join('、')">
                  {{ loc.unknown.length }} 条指令未纳入表单
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
                          :placeholder="group.multi ? '可留空表示删除' : ''"
                        />
                        <el-button
                          v-if="pickMode(name, 'location')"
                          text
                          size="small"
                          :icon="FolderOpened"
                          :title="pickMode(name, 'location') === 'folder' ? '选择文件夹' : '选择文件'"
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
                      <div v-if="!group.items.length" class="muted small">（未设置）</div>
                    </div>
                  </template>
                </div>
                <div class="add-row">
                  <el-select
                    v-model="loc.addName"
                    size="small"
                    placeholder="新增指令"
                    style="width: 200px"
                    popper-class="ngp-field-popper"
                  >
                    <el-option v-for="opt in assignable(loc)" :key="opt" :label="opt" :value="opt">
                      <span class="opt-name mono">{{ opt }}</span>
                      <span v-if="hint(opt, 'location')" class="opt-hint">{{ hint(opt, 'location') }}</span>
                    </el-option>
                  </el-select>
                  <el-button size="small" :disabled="!loc.addName" @click="addField(loc)">添加字段</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="section-title">upstream 块</div>
      <div v-if="!upstreams.length" class="empty-hint panel">没有找到 upstream 块</div>
      <div v-for="up in upstreams" :key="up.id" class="block-card panel">
        <div class="block-head" @click="up.open = !up.open">
          <el-icon class="chevron" :class="{ open: up.open }"><CaretRight /></el-icon>
          <span class="mono strong">upstream</span>
          <span class="mono">{{ up.name }}</span>
          <el-tag v-if="up.unknown?.length" size="small" type="info" :title="up.unknown.join('、')">
            {{ up.unknown.length }} 条指令未纳入表单
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
                <div v-if="!group.items.length" class="muted small">（未设置）</div>
              </div>
            </template>
          </div>
          <div class="add-row">
            <el-select
              v-model="up.addName"
              size="small"
              placeholder="新增指令"
              style="width: 200px"
              popper-class="ngp-field-popper"
            >
              <el-option v-for="opt in assignable(up)" :key="opt" :label="opt" :value="opt">
                <span class="opt-name mono">{{ opt }}</span>
                <span v-if="hint(opt, 'upstream')" class="opt-hint">{{ hint(opt, 'upstream') }}</span>
              </el-option>
            </el-select>
            <el-button size="small" :disabled="!up.addName" @click="addField(up)">添加字段</el-button>
          </div>
        </div>
      </div>
    </template>

    <el-empty v-else-if="!loading && !data" description="暂无数据" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CaretRight, Delete, FolderOpened, Refresh } from '@element-plus/icons-vue'
import { apiGet, apiPost } from '../api'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const emit = defineEmits(['applied'])

// 表单字段的中文说明：按块类型区分同名指令的含义
const HINTS = {
  server: {
    listen: '监听地址与端口，如 80、443 ssl、127.0.0.1:8080',
    server_name: '站点域名，可写多个，如 example.com *.example.com',
    root: '站点根目录，静态文件所在位置',
    index: '默认首页文件，按顺序查找，如 index.html',
    client_max_body_size: '允许上传的最大请求体，如 10m；0 表示不限制',
    ssl_certificate: 'HTTPS 证书文件路径（PEM 格式）',
    ssl_certificate_key: 'HTTPS 证书私钥文件路径',
    return: '直接返回状态码或跳转，如 301 https://$host$request_uri',
    rewrite: 'URL 重写规则，如 ^/old/(.*)$ /new/$1 permanent',
    charset: '响应字符集，如 utf-8',
    autoindex: '是否开启目录浏览，on 开启 / off 关闭',
    access_log: '访问日志路径与格式，off 表示不记录',
    error_log: '错误日志路径与级别，如 logs/error.log warn'
  },
  location: {
    proxy_pass: '反向代理目标，如 http://127.0.0.1:8080 或 http://backend',
    root: '该路径对应的文件根目录',
    index: '默认首页文件，按顺序查找',
    try_files: '按顺序尝试文件，如 $uri $uri/ /index.html',
    return: '直接返回状态码或跳转地址',
    rewrite: 'URL 重写规则，如 ^/old/(.*)$ /new/$1 permanent',
    alias: '路径别名，把 URL 路径映射到另一个目录',
    client_max_body_size: '允许上传的最大请求体，如 10m',
    proxy_read_timeout: '等待后端响应的超时时间，默认 60s',
    proxy_connect_timeout: '连接后端的超时时间，默认 60s',
    proxy_send_timeout: '向后端发送请求的超时时间，默认 60s',
    proxy_set_header: '转发给后端的请求头，如 Host $host',
    add_header: '给响应添加头部，如 X-Frame-Options SAMEORIGIN'
  },
  upstream: {
    server: '后端节点地址，如 127.0.0.1:8080，可加 weight=1 等参数',
    keepalive: '与后端保持的空闲长连接数量',
    least_conn: '负载策略：优先转发给连接数最少的后端',
    ip_hash: '负载策略：按客户端 IP 固定到同一后端',
    random: '负载策略：随机选择后端',
    hash: '负载策略：按指定键做哈希，如 hash $request_uri'
  }
}

function hint(name, scope) {
  return HINTS[scope]?.[name] || ''
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
      title: mode === 'folder' ? '选择目录' : '选择文件',
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
        throw new Error(`指令「${name}」不能为空`)
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
    ElMessage.info('没有需要保存的修改')
    return
  }
  saving.value = true
  try {
    const res = await apiPost(`/instances/${props.instanceId}/form`, {
      edits,
      inserts,
      message: '表单修改',
      reload: doReload.value
    })
    ElMessage.success(res.reloaded ? '已保存并重载 nginx' : '已保存')
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