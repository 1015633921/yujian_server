import { createApp } from 'vue'

import App from './App.vue'
import { pinia } from './app/pinia'
import { AUTH_UNAUTHORIZED_EVENT } from './api/client'
import router from './router'
import { useAuthStore } from './stores/auth'
import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)

app.use(pinia)
app.use(router)
app.mount('#app')

window.addEventListener(AUTH_UNAUTHORIZED_EVENT, () => {
  const auth = useAuthStore(pinia)
  auth.clearSession()
  if (router.currentRoute.value.name !== 'login') {
    void router.replace({
      name: 'login',
      query: { redirect: router.currentRoute.value.fullPath },
    })
  }
})
