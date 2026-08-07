<script setup lang="ts">
withDefaults(defineProps<{
  open: boolean
  title: string
  description?: string
  confirmLabel: string
  busy?: boolean
  tone?: 'default' | 'danger'
}>(), {
  description: '',
  busy: false,
  tone: 'default',
})

const emit = defineEmits<{
  close: []
  confirm: []
}>()

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="action-confirm"
      role="presentation"
      @keydown="onKeydown"
    >
      <button
        class="action-confirm__mask"
        type="button"
        aria-label="关闭确认窗口"
        :disabled="busy"
        @click="emit('close')"
      />
      <section
        class="action-confirm__panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="action-confirm-title"
      >
        <header>
          <span>OPERATION CHECK</span>
          <h2 id="action-confirm-title">
            {{ title }}
          </h2>
          <p v-if="description">
            {{ description }}
          </p>
        </header>
        <div class="action-confirm__content">
          <slot />
        </div>
        <footer>
          <button
            type="button"
            :disabled="busy"
            @click="emit('close')"
          >
            返回核对
          </button>
          <button
            type="button"
            :class="{ 'action-confirm__danger': tone === 'danger' }"
            :disabled="busy"
            autofocus
            @click="emit('confirm')"
          >
            {{ busy ? '正在提交…' : confirmLabel }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
