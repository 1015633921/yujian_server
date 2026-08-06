<template>
  <RouterView v-slot="{ Component, route }">
    <Transition
      name="route"
      mode="out-in"
    >
      <component
        :is="Component"
        :key="String(route.name || route.path)"
      />
    </Transition>
  </RouterView>
</template>
