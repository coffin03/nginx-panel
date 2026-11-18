<template>
  <div ref="host" class="editor-host"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { basicSetup } from 'codemirror'
import { Compartment, EditorState } from '@codemirror/state'
import { EditorView, keymap } from '@codemirror/view'
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from '@codemirror/language'
import { tags } from '@lezer/highlight'
import { effective } from '../theme'

const props = defineProps({
  modelValue: { type: String, default: '' },
  readonly: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'save'])

const host = ref(null)
let view = null
const readOnlyComp = new Compartment()
const themeComp = new Compartment()

// 语法配色走 CSS 变量，白天 / 夜间共用一套高亮规则
const nginxHighlight = syntaxHighlighting(
  HighlightStyle.define([
    { tag: tags.keyword, color: 'var(--ngp-syn-keyword)', fontWeight: '600' },
    { tag: [tags.string, tags.special(tags.string)], color: 'var(--ngp-syn-string)' },
    { tag: tags.comment, color: 'var(--ngp-syn-comment)', fontStyle: 'italic' },
    { tag: tags.variableName, color: 'var(--ngp-syn-var)' },
    { tag: tags.punctuation, color: 'var(--ngp-syn-punct)' },
    { tag: tags.invalid, color: 'var(--el-color-danger)' }
  ])
)

// 轻量 nginx 语法高亮：语句首词作为指令名，其余视为参数
const nginxLang = StreamLanguage.define({
  startState: () => ({ start: true }),
  token(stream, state) {
    if (stream.sol()) state.start = true
    if (stream.eatSpace()) return null
    if (stream.peek() === '#') {
      stream.skipToEnd()
      return 'comment'
    }
    if (stream.eat(';') || stream.eat('{') || stream.eat('}')) {
      state.start = true
      return 'punctuation'
    }
    if (stream.peek() === '"' || stream.peek() === "'") {
      const quote = stream.next()
      while (!stream.eol()) {
        const ch = stream.next()
        if (ch === '\\') {
          stream.next()
          continue
        }
        if (ch === quote) break
      }
      state.start = false
      return 'string'
    }
    if (stream.match(/^\$[\w]+/)) {
      state.start = false
      return 'variableName'
    }
    if (!stream.match(/^[^\s;{}#]+/)) {
      stream.next()
      return null
    }
    if (state.start) {
      state.start = false
      return 'keyword'
    }
    return 'variableName'
  }
})

const editorTheme = (dark) =>
  EditorView.theme(
    {
      '&': { height: '100%', backgroundColor: 'var(--ngp-surface)', color: 'var(--ngp-text)' },
      '.cm-scroller': { overflow: 'auto' },
      '.cm-gutters': {
        backgroundColor: 'var(--ngp-surface-2)',
        color: 'var(--ngp-muted)',
        border: 'none'
      },
      '.cm-lineNumbers .cm-gutterElement': { padding: '0 10px 0 14px' },
      '.cm-activeLine': { backgroundColor: dark ? 'rgba(52, 211, 153, 0.07)' : 'rgba(15, 157, 117, 0.06)' },
      '.cm-activeLineGutter': {
        backgroundColor: dark ? 'rgba(52, 211, 153, 0.1)' : 'rgba(15, 157, 117, 0.08)',
        color: 'var(--ngp-brand)'
      },
      '.cm-content': { caretColor: 'var(--ngp-brand)', padding: '8px 0' },
      '.cm-cursor': { borderLeftColor: 'var(--ngp-brand)' },
      '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection': {
        backgroundColor: dark ? 'rgba(52, 211, 153, 0.22)' : 'rgba(15, 157, 117, 0.18)'
      },
      '.cm-matchingBracket': {
        backgroundColor: 'var(--ngp-brand-soft)',
        outline: '1px solid var(--ngp-brand-ring)'
      },
      '.cm-searchMatch': { backgroundColor: dark ? 'rgba(250, 204, 21, 0.28)' : 'rgba(250, 204, 21, 0.35)' },
      '.cm-panels': {
        backgroundColor: 'var(--ngp-surface-2)',
        color: 'var(--ngp-text)',
        borderColor: 'var(--ngp-border)'
      },
      '.cm-tooltip': {
        backgroundColor: 'var(--ngp-surface)',
        border: '1px solid var(--ngp-border)',
        color: 'var(--ngp-text)'
      }
    },
    { dark }
  )

const saveKeymap = keymap.of([
  {
    key: 'Mod-s',
    preventDefault: true,
    run: () => {
      emit('save')
      return true
    }
  }
])

onMounted(() => {
  view = new EditorView({
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        basicSetup,
        nginxLang,
        nginxHighlight,
        EditorView.lineWrapping,
        readOnlyComp.of(EditorState.readOnly.of(props.readonly)),
        saveKeymap,
        themeComp.of(editorTheme(effective.value === 'dark')),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) emit('update:modelValue', update.state.doc.toString())
        })
      ]
    }),
    parent: host.value
  })
})

watch(
  () => props.modelValue,
  (value) => {
    if (!view) return
    const current = view.state.doc.toString()
    if (value !== current) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: value || '' } })
    }
  }
)

watch(
  () => props.readonly,
  (value) => {
    if (view) view.dispatch({ effects: readOnlyComp.reconfigure(EditorState.readOnly.of(value)) })
  }
)

watch(effective, (mode) => {
  if (view) view.dispatch({ effects: themeComp.reconfigure(editorTheme(mode === 'dark')) })
})

onBeforeUnmount(() => {
  view?.destroy()
  view = null
})

defineExpose({ focus: () => view?.focus() })
</script>

<style scoped>
.editor-host {
  height: 100%;
  min-height: 200px;
  overflow: hidden;
  border: 1px solid var(--ngp-border);
  border-radius: 10px;
  background: var(--ngp-surface);
  transition: border-color 0.2s ease, background-color 0.25s ease;
}
.editor-host:focus-within {
  border-color: var(--ngp-brand);
  box-shadow: 0 0 0 3px var(--ngp-brand-ring);
}
.editor-host :deep(.cm-editor) {
  height: 100%;
}
.editor-host :deep(.cm-editor.cm-focused) {
  outline: none;
}
</style>