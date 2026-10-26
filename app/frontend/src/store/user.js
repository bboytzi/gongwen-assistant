import { defineStore } from 'pinia'
import api from '../api'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: null,
  }),
  getters: {
    isLoggedIn: state => !!state.token,
    isAdmin: state => state.user?.role === 'admin',
    // 界面展示优先用中文显示名，没设则回退登录名
    shownName: state => state.user?.display_name || state.user?.username || '',
  },
  actions: {
    async login(username, password) {
      const data = await api.post('/auth/login', { username, password })
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', this.token)
    },
    async register(username, password, displayName, department) {
      const data = await api.post('/auth/register', {
        username,
        password,
        display_name: displayName || null,
        department,
      })
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', this.token)
    },
    async fetchMe() {
      if (!this.token) return
      try {
        this.user = await api.get('/auth/me')
      } catch {
        this.logout()
      }
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
    },
  },
})
