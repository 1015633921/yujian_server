<script setup lang="ts">
import type { MaterialOption } from '@/features/materials/api'

const props = defineProps<{
  modelValue: string[]
  options: Array<MaterialOption & { unavailable?: boolean }>
  disabled?: boolean
  ariaLabel: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

function toggle(key: string, checked: boolean): void {
  const next = checked
    ? [...new Set([...props.modelValue, key])]
    : props.modelValue.filter((item) => item !== key)
  emit('update:modelValue', next)
}
</script>

<template>
  <fieldset
    class="material-option-checks"
    :aria-label="ariaLabel"
    :disabled="disabled"
  >
    <label
      v-for="option in options"
      :key="option.key"
      :class="{ 'is-unavailable': option.unavailable }"
    >
      <input
        type="checkbox"
        :checked="modelValue.includes(option.key)"
        @change="toggle(option.key, ($event.target as HTMLInputElement).checked)"
      >
      <span>{{ option.label }}</span>
      <small v-if="option.unavailable">已停用，请取消或替换</small>
    </label>
    <p v-if="!options.length">
      暂无可用选项，请先到材料字段字典维护。
    </p>
  </fieldset>
</template>
