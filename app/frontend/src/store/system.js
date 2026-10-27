import { defineStore } from 'pinia'
import api from '../api'

const FALLBACK_NAME = '公文辅助系统'
const FALLBACK_SUBTITLE = '公文起草 · 制度检索 · 知识库'

export const useSystemStore = defineStore('system', {
  state: () => ({
    name: FALLBACK_NAME,
    subtitle: FALLBACK_SUBTITLE,
    logo: null,          // data URL；null 表示用内置方印
    loaded: false,
  }),
  actions: {
    async load() {
      try {
        const data = await api.get('/settings/public')
        this.name = data.system_name || FALLBACK_NAME
        this.subtitle = data.system_subtitle || FALLBACK_SUBTITLE
        this.logo = data.system_logo || null
      } catch {
        // 后端不可用时用默认值，不影响登录页渲染
        this.name = FALLBACK_NAME
        this.subtitle = FALLBACK_SUBTITLE
        this.logo = null
      }
      this.loaded = true
      document.title = this.name
    },

    apply(data) {
      if (!data) return
      this.name = data.system_name || FALLBACK_NAME
      this.subtitle = data.system_subtitle || FALLBACK_SUBTITLE
      this.logo = data.system_logo || null
      document.title = this.name
    },
  },
})
