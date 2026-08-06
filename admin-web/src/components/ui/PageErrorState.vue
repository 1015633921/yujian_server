<script setup lang="ts">
defineProps<{
  title: string
  message: string
  eyebrow?: string
}>()

defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="page-state page-state--error">
    <span>{{ eyebrow || 'DATA UNAVAILABLE' }}</span>
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <button
      type="button"
      @click="$emit('retry')"
    >
      重新加载
    </button>
  </div>
</template>
