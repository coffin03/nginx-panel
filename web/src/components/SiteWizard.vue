<template>
  <el-dialog :model-value="modelValue" :title="t('site.dialogTitle')" width="780px" top="6vh" @update:model-value="close">
    <div class="wizard">
      <el-form label-width="92px" label-position="left" size="small" class="form">
        <el-form-item :label="t('site.name')" required>
          <el-input v-model="form.server_name" :placeholder="t('site.namePlaceholder')" />
        </el-form-item>

        <el-form-item :label="t('site.kind')">
          <el-radio-group v-model="form.kind">
            <el-radio label="static">{{ t('site.kindStatic') }}</el-radio>
            <el-radio label="proxy">{{ t('site.kindProxy') }}</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="form.kind === 'static'" :label="t('site.root')" required>
          <PathInput v-model="form.root" mode="folder" :title="t('site.root')" />
        </el-form-item>

        <el-form-item v-else :label="t('site.proxyPass')" required>
          <el-input v-model="form.proxy_pass" :placeholder="t('site.proxyPlaceholder')" />
        </el-form-item>

        <el-form-item :label="t('site.listen')">
          <el-input-number v-model="form.listen" :min="1" :max="65535" controls-position="right" style="width: 150px" />
        </el-form-item>

        <el-form-item :label="t('site.ssl')">
          <el-switch v-model="form.ssl" />
        </el-form-item>

        <template v-if="form.ssl">
          <el-form-item :label="t('site.certificate')" required>
            <PathInput v-model="form.ssl_certificate" mode="file" />
          </el-form-item>
          <el-form-item :label="t('site.certificateKey')" required>
            <PathInput v-model="form.ssl_certificate_key" mode="file" />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.redirect_http">{{ t('site.redirectHttp') }}</el-checkbox>
            <el-input-number
              v-if="form.redirect_http"
              v-model="form.redirect_port"
              :min="1"
              :max="65535"
              size="small"
              controls-position="right"
              style="width: 110px; margin-left: 10px"
            />
          </el-form-item>
        </template>

        <el-form-item>
          <el-button text type="primary" @click="advanced = !advanced">{{ t('site.advanced') }}</el-button>
        </el-form-item>

        <template v-if="advanced">
          <el-form-item :label="t('site.location')">
            <el-input v-model="form.location" placeholder="/" />
          </el-form-item>
          <el-form-item :label="t('site.filename')">
            <el-input v-model="form.filename" :placeholder="t('site.filenamePlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('site.accessLog')">
            <el-input v-model="form.access_log" :placeholder="t('site.logPlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('site.errorLog')">
            <el-input v-model="form.error_log" :placeholder="t('site.logPlaceholder')" />
          </el-form-item>
        </template>
      </el-form>

      <div class="preview-side">
        <div class="preview-head">
          <span class="label">{{ t('site.previewTitle') }}</span>
          <span v-if="previewRel" class="mono small muted">{{ previewRel }}</span>
          <span class="grow"></span>
          <el-button size="small" :loading="previewing" @click="doPreview">{{ t('site.preview') }}</el-button>
        </div>
        <el-alert
          v-if="previewWarnings.length"
          type="warning"
          :closable="false"
          show-icon
          :title="previewWarnings.join('；')"
          class="preview-warn"
        />
        <pre class="preview mono">{{ previewText || t('site.previewTip') }}</pre>
      </div>
    </div>

    <template #footer>
      <el-button @click="close">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">{{ t('site.submit') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api'
import PathInput from './PathInput.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  instanceId: { type: [Number, String], required: true }
})
const emit = defineEmits(['update:modelValue', 'created'])
const { t } = useI18n()

const advanced = ref(false)
const previewing = ref(false)
const submitting = ref(false)
const previewText = ref('')
const previewRel = ref('')
const previewWarnings = ref([])

function blank() {
  return {
    server_name: '',
    kind: 'static',
    root: '',
    proxy_pass: '',
    location: '/',
    listen: 80,
    redirect_http: true,
    redirect_port: 80,
    ssl: false,
    ssl_certificate: '',
    ssl_certificate_key: '',
    access_log: '',
    error_log: '',
    index: 'index.html index.htm',
    filename: ''
  }
}

const form = reactive(blank())

function payload() {
  return {
    ...form,
    listen: Number(form.listen) || 80,
    redirect_port: Number(form.redirect_port) || 80
  }
}

function reset() {
  Object.assign(form, blank())
  advanced.value = false
  previewText.value = ''
  previewRel.value = ''
  previewWarnings.value = []
}

function close() {
  emit('update:modelValue', false)
}

async function doPreview() {
  previewing.value = true
  try {
    const res = await apiPost(`/instances/${props.instanceId}/sites/preview`, payload())
    previewText.value = res.content
    previewRel.value = res.rel
    previewWarnings.value = res.warnings || []
  } catch (e) {
    previewText.value = ''
  } finally {
    previewing.value = false
  }
}

async function submit() {
  submitting.value = true
  try {
    const res = await apiPost(`/instances/${props.instanceId}/sites`, payload())
    ElMessage.success(t('site.created', { path: res.rel || '' }))
    const warns = (res.warnings || []).map((w) => (typeof w === 'string' ? w : w.message)).filter(Boolean)
    if (warns.length) ElMessage.warning(warns.join('；'))
    emit('created', res)
    close()
  } catch (e) {
    /* 错误已由全局提示 */
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    // 打开时只重置表单，校验留到用户点击「预览」或「创建」时进行
    if (visible) reset()
  }
)
</script>

<style scoped>
.wizard {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.form {
  min-width: 0;
}
.preview-side {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}
.preview-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ngp-text-2);
}
.preview-warn {
  padding: 6px 10px;
}
.preview {
  margin: 0;
  padding: 10px 12px;
  min-height: 280px;
  max-height: 46vh;
  overflow: auto;
  font-size: 12px;
  line-height: 1.55;
  background: var(--ngp-surface-2);
  border: 1px solid var(--ngp-border-soft);
  border-radius: 10px;
  white-space: pre;
}
.small {
  font-size: 12px;
}
.muted {
  color: var(--ngp-muted);
}
@media (max-width: 860px) {
  .wizard {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>