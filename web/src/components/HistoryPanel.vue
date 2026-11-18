<template>
  <div class="history-panel">
    <div class="toolbar">
      <el-button :icon="Refresh" @click="load">刷新</el-button>
      <span class="muted">每次应用配置都会自动生成快照，可对比差异并一键回滚</span>
    </div>

    <el-table v-loading="loading" :data="snapshots" size="small" class="table" @row-click="openDetail">
      <el-table-column prop="created_at" label="时间" width="165" />
      <el-table-column prop="message" label="说明" min-width="200" show-overflow-tooltip />
      <el-table-column label="来源" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ triggerLabel(row.trigger) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="operator" label="操作人" width="110" align="center" />
      <el-table-column prop="file_count" label="文件" width="70" align="center" />
      <el-table-column label="校验" width="80" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.test_ok === 1" size="small" type="success">通过</el-tag>
          <el-tag v-else-if="row.test_ok === 0" size="small" type="danger">失败</el-tag>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="136" align="center">
        <template #default="{ row }">
          <div class="ops">
            <el-button size="small" text type="primary" @click.stop="openDetail(row)">查看</el-button>
            <el-button size="small" text type="warning" @click.stop="restore(row)">回滚</el-button>
          </div>
        </template>
      </el-table-column>
      <template #empty>
        <div class="empty-hint">暂无历史快照</div>
      </template>
    </el-table>

    <el-drawer v-model="drawer" title="快照详情" size="60%" destroy-on-close append-to-body>
      <template v-if="detail">
        <div class="detail-head">
          <div>
            <div class="mono">{{ detail.created_at }} · {{ triggerLabel(detail.trigger) }}</div>
            <div class="muted">{{ detail.message }}</div>
          </div>
          <el-button type="warning" plain :loading="restoring" @click="restore(detail)">回滚到此快照</el-button>
        </div>
        <el-radio-group v-model="currentPath" size="small" class="file-tabs" @change="loadDiff">
          <el-radio-button v-for="file in detail.files" :key="file.path" :value="file.path">
            {{ shortName(file.path) }}
          </el-radio-button>
        </el-radio-group>
        <div class="diff-hint muted">
          <span class="mono">{{ currentPath }}</span>
          <span>· 绿色为当前新增，红色为快照中被删除</span>
        </div>
        <pre v-if="diff" class="diff-view"><span
          v-for="(line, idx) in diffLines"
          :key="idx"
          :class="line.cls"
        >{{ line.text }}</span></pre>
        <div v-else class="empty-hint">{{ diffLoading ? '正在计算差异…' : '该文件与当前内容一致' }}</div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { apiGet, apiPost } from '../api'

const props = defineProps({
  instanceId: { type: [Number, String], required: true }
})
const emit = defineEmits(['restored'])

const loading = ref(false)
const snapshots = ref([])
const drawer = ref(false)
const detail = ref(null)
const currentPath = ref('')
const diff = ref('')
const diffLoading = ref(false)
const restoring = ref(false)

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
  return (
    {
      manual: '手动',
      editor: '编辑器',
      form: '表单',
      batch: '批量',
      restore: '回滚',
      auto: '外部修改',
      system: '系统'
    }[trigger] || trigger || '其他'
  )
}

function shortName(path) {
  const parts = path.replace(/\\/g, '/').split('/')
  return parts.slice(-2).join('/')
}

async function load() {
  loading.value = true
  try {
    snapshots.value = await apiGet(`/instances/${props.instanceId}/snapshots?limit=100`)
  } catch (e) {
    /* 已提示 */
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function openDetail(row) {
  try {
    detail.value = await apiGet(`/instances/${props.instanceId}/snapshots/${row.id}`)
    drawer.value = true
    diff.value = ''
    currentPath.value = detail.value.files?.[0]?.path || ''
    if (currentPath.value) await loadDiff()
  } catch (e) {
    /* 已提示 */
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
    await ElMessageBox.confirm(
      `将把配置恢复到「${row.created_at}」的快照状态，并自动校验；当前未保存的修改会丢失。`,
      '回滚配置',
      { type: 'warning', confirmButtonText: '回滚', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }
  restoring.value = true
  try {
    const res = await apiPost(`/instances/${props.instanceId}/snapshots/${row.id}/restore`, { reload: true })
    ElMessage.success(res.reloaded ? '已回滚并重载 nginx' : '已回滚配置')
    drawer.value = false
    await load()
    emit('restored', res)
  } catch (e) {
    /* 已提示 */
  } finally {
    restoring.value = false
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
</style>