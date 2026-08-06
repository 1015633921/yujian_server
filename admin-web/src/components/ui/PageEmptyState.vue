<script setup lang="ts">
defineProps<{
  title: string
  message: string
}>()

defineEmits<{
  clear: []
}>()
</script>

<template>
  <div class="page-empty-state">
    <span>NO REQUESTS</span>
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <button
      v-if="$slots.action"
      type="button"
      @click="$emit('clear')"
    >
      <slot name="action" />
    </button>
  </div>
</template>
