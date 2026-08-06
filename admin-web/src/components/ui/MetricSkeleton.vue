<script setup lang="ts">
withDefaults(
  defineProps<{
    count?: number
    label?: string
  }>(),
  {
    count: 4,
    label: '正在加载数据',
  },
)
</script>

<template>
  <div
    class="loading-lines"
    role="status"
    :aria-label="label"
  >
    <i
      v-for="item in count"
      :key="item"
    />
  </div>
</template>
