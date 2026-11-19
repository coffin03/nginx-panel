<template>
  <div class="logs-panel">
    <div class="toolbar">
      <el-select v-model="current" size="small" :placeholder="t('logs.select')" style="width: 260px" @change="loadTail">
        <el-option v-for="file in files" :key="file.path" :label="`${file.name} (${humanSize(file.size)})`" :value="file.path" />
      </el-select>
      <el-select v-model="lines" size="small" style="width: 110px" @change="loadTail">
        <el-option v-for="n in [100, 200, 500, 1000, 2000]" :key="n" :label="t('logs.lines', { n })" :value="n" />
      </el-select>
      <el-button size="small" :icon="Refresh" :loading="refreshing" @click="loadAll">{{ t('common.refresh') }}</el-button>
      <el-checkbox v-model="auto" size="small">{{ t('logs.auto') }}</el-checkbox>
      <el-input v-model="keyword" size="small" :placeholder="t('logs.filter')" clearable style="width: 180px" />
      <span class="grow"></span>
      <span v-if="truncated" class="muted small">{{ t('logs.tailOnly', { n: lines }) }}</span>
    </div>

    <div v-if="!files.length" class="empty-hint panel">{{ t('logs.empty') }}</div>
    <pre v-else class="log-view mono">{{ shownText || t('logs.noContent') }}</pre>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import { apiGet } from '../api'
import { holdLoading } from '../utils/busy'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const { t } = useI18n()

const files = ref([])
const current = ref('')
const lines = ref(200)
const auto = ref(false)
const keyword = ref('')
const content = ref([])
const truncated = ref(false)
const loading = ref(false)
const refreshing = ref(false)
let timer = null

const shownText = computed(() => {
  if (!keyword.value.trim()) return content.value.join('\n')
  const kw = keyword.value.trim().toLowerCase()
  return content.value.filter((line) => line.toLowerCase().includes(kw)).join('\n')
})

function humanSize(size) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

async function loadFiles() {
  try {
    const res = await apiGet(`/instances/${props.instanceId}/logs`)
    files.value = res.files || []
    if (!current.value && files.value.length) {
      const preferred = files.value.find((f) => f.name === 'error.log') || files.value[0]
      current.value = preferred.path
    }
  } catch (e) {
    /* 已提示 */
  }
}

async function loadTail() {
  if (!current.value) return
  loading.value = true
  try {
    const res = await apiGet(
      `/instances/${props.instanceId}/logs/tail?name=${encodeURIComponent(current.value)}&lines=${lines.value}`
    )
    content.value = res.lines || []
    truncated.value = !!res.truncated
  } catch (e) {
    content.value = []
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  const started = Date.now()
  refreshing.value = true
  try {
    await loadFiles()
    await loadTail()
  } finally {
    await holdLoading(started)
    refreshing.value = false
  }
}

function setupTimer() {
  clearInterval(timer)
  if (auto.value) timer = setInterval(loadTail, 3000)
}

watch(auto, setupTimer)

onMounted(async () => {
  await loadAll()
})

onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.logs-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  min-height: 0;
}
.toolbar {
  padding-bottom: 2px;
  flex: none;
}
.small {
  font-size: 12px;
}
.log-view {
  margin: 0;
  padding: 12px 14px;
  flex: 1;
  min-height: 0;
  max-height: none;
  height: auto;
}
.empty-hint {
  padding: 24px;
}
</style>