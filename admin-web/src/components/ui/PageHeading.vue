<script setup lang="ts">
defineProps<{
  eyebrow: string
  title: string
  description?: string
}>()
</script>

<template>
  <header class="workspace-heading">
    <div>
      <span>{{ eyebrow }}</span>
      <h1>{{ title }}</h1>
      <p v-if="description">
        {{ description }}
      </p>
    </div>
    <div
      v-if="$slots.actions"
      class="workspace-heading__actions"
    >
      <slot name="actions" />
    </div>
  </header>
</template>
