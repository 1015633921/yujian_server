<script setup lang="ts">
import { legacyAdminPath } from '@/runtime/environment'
</script>

<template>
  <main class="not-found-page">
    <span>404 · ROUTE NOT FOUND</span>
    <h1>这个新版页面还没有建立。</h1>
    <p>返回经营概览，或者继续使用当前运营后台。</p>
    <div>
      <RouterLink to="/overview">
        返回概览
      </RouterLink>
      <a :href="legacyAdminPath()">当前后台</a>
    </div>
  </main>
</template>
