import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    children: [
      {
        path: '',
        name: 'Home',
        component: () => import('../views/Home.vue'),
      },
      {
        path: 'documents/new',
        name: 'NewDocument',
        component: () => import('../views/NewDocument.vue'),
      },
      {
        path: 'documents/:id/generate',
        name: 'GenerateProgress',
        component: () => import('../views/GenerateProgress.vue'),
      },
      {
        path: 'documents/:id/edit',
        name: 'Editor',
        component: () => import('../views/Editor.vue'),
      },
      {
        path: 'search',
        name: 'Search',
        component: () => import('../views/Search.vue'),
      },
      {
        path: 'knowledge',
        name: 'Knowledge',
        component: () => import('../views/Knowledge.vue'),
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/Settings.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
