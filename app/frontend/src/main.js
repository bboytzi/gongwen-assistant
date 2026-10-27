import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router'
import { useSystemStore } from './store/system'
import './assets/main.css'

const app = createApp(App)
const pinia = createPinia()

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// 拉取系统名称与 logo，登录页也要用，所以不依赖登录状态。
// 异步执行不阻塞挂载，未返回时先用 store 里的默认值。
useSystemStore().load()

app.mount('#app')
