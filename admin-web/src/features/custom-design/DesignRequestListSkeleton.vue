<template>
  <div
    class="design-list-skeleton"
    role="status"
    aria-label="正在加载人工搭配工单"
  >
    <i
      v-for="row in 6"
      :key="row"
    />
  </div>
</template>
