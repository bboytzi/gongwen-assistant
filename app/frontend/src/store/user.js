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
  },
  actions: {
    async login(username, password) {
      const data = await api.post('/auth/login', { username, password })
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('token', this.token)
    },
    async register(username, password, department) {
      const data = await api.post('/auth/register', { username, password, department })
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
