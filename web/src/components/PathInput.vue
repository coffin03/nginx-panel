<template>
  <el-input v-model="text" :placeholder="placeholder" :disabled="disabled" @update:model-value="onInput">
    <template #append>
      <el-button :icon="FolderOpened" :loading="busy" :disabled="disabled" @click="browse">{{ t('common.browse') }}</el-button>
    </template>
  </el-input>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { FolderOpened } from '@element-plus/icons-vue'
import { apiPost } from '../api'

const props = defineProps({
  modelValue: { type: String, default: '' },
  mode: { type: String, default: 'file' },
  placeholder: { type: String, default: '' },
  title: { type: String, default: '' },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const text = ref(props.modelValue || '')
const busy = ref(false)

watch(
  () => props.modelValue,
  (v) => {
    text.value = v || ''
  }
)

function onInput(value) {
  emit('update:modelValue', value)
}

function initialDir() {
  const v = (props.modelValue || '').trim()
  if (!v) return ''
  return props.mode === 'folder' ? v : v.replace(/[\\/][^\\/]*$/, '')
}

async function browse() {
  busy.value = true
  try {
    const res = await apiPost('/system/pick', {
      mode: props.mode,
      title: props.title || (props.mode === 'folder' ? t('form.pickFolder') : t('form.pickFile')),
      initial: initialDir()
    })
    if (res?.path) {
      text.value = res.path
      emit('update:modelValue', res.path)
    }
  } catch (e) {
    /* 错误已由全局提示 */
  } finally {
    busy.value = false
  }
}
</script>