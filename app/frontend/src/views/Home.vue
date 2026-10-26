<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">工作台 / 首页</div>
        <h1 class="page-title">{{ greeting }}，{{ userStore.shownName }}</h1>
        <div class="page-sub">{{ subline }}</div>
      </div>
      <div class="head-actions">
        <el-button @click="$router.push('/knowledge')">上传制度</el-button>
        <el-button type="primary" @click="$router.push('/documents/new')">新建请示</el-button>
      </div>
    </div>

    <div class="stats">
      <div v-for="s in statCards" :key="s.label" class="stat card">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value" :style="{ color: s.color || 'var(--ink)' }">{{ s.value }}</div>
        <div class="stat-note">{{ s.note }}</div>
      </div>
    </div>

    <div class="quick">
      <div
        v-for="q in quicks"
        :key="q.title"
        class="quick-card card"
        @click="$router.push(q.to)"
      >
        <div class="quick-icon" :style="{ background: q.bg, color: q.color }">
          <el-icon><component :is="q.icon" /></el-icon>
        </div>
        <div class="quick-body">
          <div class="quick-title">{{ q.title }}</div>
          <div class="quick-sub">{{ q.sub }}</div>
        </div>
      </div>
    </div>

    <div class="card list">
      <div class="list-head">
        <span class="card-title">最近请示</span>
        <span class="list-count">共 {{ documents.length }} 篇</span>
      </div>

      <el-table :data="documents" v-loading="loading" style="width: 100%">
        <el-table-column prop="title" label="标题" min-width="240">
          <template #default="{ row }">
            <span class="doc-title" @click="goDoc(row)">{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="doc_category" label="类型" width="88">
          <template #default="{ row }">{{ categoryText(row.doc_category) }}</template>
        </el-table-column>
        <el-table-column prop="procurement_method" label="采购方式" width="96">
          <template #default="{ row }">{{ methodText(row.procurement_method) }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="88">
          <template #default="{ row }">
            <span class="status" :style="statusStyle(row.status)">{{ statusText(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="updated_at" label="更新时间" width="140">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="76">
          <template #default="{ row }">
            <span class="action" @click="goDoc(row)">{{ actionText(row.status) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <div class="empty">
            <div class="empty-text">还没有请示材料</div>
            <el-button type="primary" size="small" @click="$router.push('/documents/new')">
              新建第一篇
            </el-button>
          </div>
        </template>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { EditPen, Upload, Search } from '@element-plus/icons-vue'
import api from '../api'
import { useUserStore } from '../store/user'
import dayjs from 'dayjs'

const router = useRouter()
const userStore = useUserStore()

const documents = ref([])
const loading = ref(false)
const stats = ref(null)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const subline = computed(() => {
  const n = stats.value?.generating || 0
  if (n > 0) return `有 ${n} 份请示正在生成`
  const total = stats.value?.total_documents || 0
  if (total === 0) return '还没有请示材料，从新建一篇开始'
  return '所有请示均已完成'
})

const statCards = computed(() => {
  const s = stats.value || {}
  return [
    {
      label: '本月请示',
      value: s.month_documents ?? 0,
      note: `累计 ${s.total_documents ?? 0} 篇`,
    },
    {
      label: '生成中',
      value: s.generating ?? 0,
      note: s.generating ? '等待模型出稿' : '暂无任务',
      color: s.generating ? 'var(--warn)' : undefined,
    },
    {
      label: '制度文档',
      value: s.kb_documents ?? 0,
      note: `${s.kb_chunks ?? 0} 个分块`,
    },
    {
      label: '已完成',
      value: s.completed ?? 0,
      note: s.vector_ready ? '语义检索已启用' : '仅关键词检索',
      color: 'var(--ok)',
    },
  ]
})

const quicks = [
  {
    title: '新建请示',
    sub: '采购 / 人事 / 资金 / 项目',
    to: '/documents/new',
    icon: EditPen,
    bg: 'var(--seal-soft)',
    color: 'var(--seal)',
  },
  {
    title: '上传制度',
    sub: 'PDF / Word 自动解析入库',
    to: '/knowledge',
    icon: Upload,
    bg: 'var(--gold-soft)',
    color: 'var(--gold)',
  },
  {
    title: '检索材料',
    sub: '语义 / 关键词双模式',
    to: '/search',
    icon: Search,
    bg: 'var(--ok-soft)',
    color: 'var(--ok)',
  },
]

onMounted(async () => {
  loading.value = true
  try {
    const [list, st] = await Promise.all([
      api.get('/documents'),
      api.get('/stats').catch(() => null),
    ])
    documents.value = list || []
    stats.value = st
  } finally {
    loading.value = false
  }
})

function goDoc(row) {
  const path = row.status === 'done'
    ? `/documents/${row.id}/edit`
    : `/documents/${row.id}/generate`
  router.push(path)
}

function actionText(status) {
  if (status === 'done') return '编辑'
  if (status === 'generating') return '进度'
  return '生成'
}

function categoryText(c) {
  return {
    procurement: '采购类', personnel: '人事类', fund: '资金类',
    project: '项目类', regulation: '制度类',
  }[c] || c || '-'
}

function methodText(m) {
  return { direct: '直接委托', inquiry: '询价', open: '公开采购', tender: '招标' }[m] || '-'
}

function statusText(s) {
  return { draft: '草稿', generating: '生成中', done: '已完成', failed: '失败' }[s] || s
}

function statusStyle(s) {
  const map = {
    done: { color: 'var(--ok)', background: 'var(--ok-soft)' },
    generating: { color: 'var(--warn)', background: 'var(--warn-soft)' },
    failed: { color: 'var(--err)', background: 'var(--err-soft)' },
    draft: { color: 'var(--ink-3)', background: 'var(--paper-2)' },
  }
  return map[s] || map.draft
}

function formatDate(d) {
  return d ? dayjs(d).format('MM-DD HH:mm') : '-'
}
</script>

<style scoped>
.head-actions {
  margin-left: auto;
  display: flex;
  gap: 9px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.stat {
  padding: 13px 15px;
}

.quick {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.quick-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.quick-card:hover {
  border-color: var(--gold-line);
}

.quick-icon {
  width: 34px;
  height: 34px;
  border-radius: var(--r-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}

.quick-title {
  font-size: 13px;
  color: var(--ink);
}

.quick-sub {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 2px;
}

.list {
  overflow: hidden;
}

.list-head {
  display: flex;
  align-items: center;
  padding: 13px 16px 11px;
  border-bottom: 0.5px solid var(--line-2);
}

.list-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--ink-4);
}

.doc-title {
  font-size: 13px;
  color: var(--ink);
  cursor: pointer;
}

.doc-title:hover {
  color: var(--seal);
}

.status {
  display: inline-block;
  padding: 1px 8px;
  border-radius: var(--r-sm);
  font-size: 11px;
}

.action {
  font-size: 12px;
  color: var(--seal);
  cursor: pointer;
}

.action:hover {
  text-decoration: underline;
}

.empty {
  padding: 34px 0 38px;
  text-align: center;
}

.empty-text {
  font-size: 12px;
  color: var(--ink-4);
  margin-bottom: 12px;
}
</style>
