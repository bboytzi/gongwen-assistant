<template>
  <div class="page">
    <div class="page-head">
      <div>
        <div class="crumb">工作台 / 检索中心</div>
        <h1 class="page-title">检索中心</h1>
        <div class="page-sub">按语义或关键词查找制度条款与历史公文</div>
      </div>
    </div>

    <div class="search-bar card">
      <el-select v-model="mode" class="mode">
        <el-option label="语义检索" value="hybrid" />
        <el-option label="关键词" value="keyword" />
      </el-select>
      <input
        v-model="query"
        class="search-input"
        placeholder="输入自然语言描述，例如：采购办公设备的审批流程"
        @keyup.enter="handleSearch"
      />
      <el-button type="primary" :loading="searching" @click="handleSearch">检索</el-button>
    </div>

    <div class="layout">
      <div class="filter-col">
        <div class="card card-pad">
          <div class="card-title">检索范围</div>
          <div class="filter-group">
            <label v-for="kb in allKbs" :key="kb.id" class="check">
              <input type="checkbox" :value="kb.id" v-model="filters.kb_ids" />
              <span>{{ kb.name }}</span>
            </label>
            <div v-if="allKbs.length === 0" class="filter-empty">暂无知识库</div>
          </div>

          <div class="divider"></div>

          <div class="card-title">文档类型</div>
          <div class="filter-group">
            <label v-for="t in docTypes" :key="t.value" class="check">
              <input type="checkbox" :value="t.value" v-model="filters.doc_types" />
              <span>{{ t.label }}</span>
            </label>
          </div>
        </div>
      </div>

      <div class="result-col">
        <div v-if="searched" class="result-meta">
          找到 {{ results.length }} 条结果
          <span v-if="elapsed">· 耗时 {{ elapsed }} ms</span>
        </div>

        <div v-if="results.length === 0 && searched && !searching" class="empty card">
          <div class="empty-text">没有找到相关内容</div>
          <div class="empty-sub">试试换个说法，或放宽检索范围</div>
        </div>

        <div v-loading="searching" class="results">
          <div v-for="(r, i) in results" :key="i" class="result card">
            <div class="result-head">
              <span class="result-type" :style="typeStyle(r.doc_type)">
                {{ r.doc_type === 'regulation' ? '管理办法' : '历史公文' }}
              </span>
              <span class="result-title">{{ r.title }}</span>
              <span class="result-score">{{ Math.round((r.score || 0) * 100) }}%</span>
            </div>
            <div class="result-body">{{ (r.content || '').substring(0, 180) }}…</div>
            <div class="result-foot">{{ r.source || '' }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const query = ref(route.query.q || '')
const mode = ref('hybrid')
const searching = ref(false)
const searched = ref(false)
const results = ref([])
const elapsed = ref(0)

const companyKbs = ref([])
const personalKbs = ref([])

const allKbs = computed(() => [...companyKbs.value, ...personalKbs.value])

const docTypes = [
  { label: '管理办法', value: 'regulation' },
  { label: '公文材料', value: 'case' },
  { label: '模板', value: 'template' },
]

const filters = ref({
  kb_ids: [],
  doc_types: [],
})

onMounted(async () => {
  try {
    const data = await api.get('/kb/bases')
    companyKbs.value = data.company || []
    personalKbs.value = data.personal || []
    filters.value.kb_ids = allKbs.value.map(k => k.id)
  } catch { /* 知识库拉取失败时用全部范围检索 */ }

  if (query.value) handleSearch()
})

async function handleSearch() {
  if (!query.value.trim()) return
  searching.value = true
  searched.value = true
  try {
    const data = await api.post('/search', {
      query: query.value,
      mode: mode.value,
      scope: filters.value.kb_ids,
      doc_types: filters.value.doc_types,
      limit: 20,
    })
    results.value = data.results || []
    elapsed.value = data.elapsed_ms || 0
  } catch {
    results.value = []
  } finally {
    searching.value = false
  }
}

function typeStyle(t) {
  return t === 'regulation'
    ? { color: 'var(--seal)', background: 'var(--seal-soft)' }
    : { color: 'var(--ok)', background: 'var(--ok-soft)' }
}
</script>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 13px;
  margin-bottom: 16px;
}

.mode {
  width: 108px;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  min-width: 0;
  height: 32px;
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
  font-size: 13px;
  color: var(--ink);
}

.search-input::placeholder {
  color: var(--ink-4);
}

.layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.filter-col {
  width: 210px;
  flex-shrink: 0;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 9px;
}

.check {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  color: var(--ink-2);
  cursor: pointer;
}

.check input {
  accent-color: var(--seal);
  margin: 0;
}

.filter-empty {
  font-size: 11px;
  color: var(--ink-4);
}

.divider {
  height: 1px;
  background: var(--line-2);
  margin: 16px 0;
}

.result-col {
  flex: 1;
  min-width: 0;
}

.result-meta {
  font-size: 11px;
  color: var(--ink-4);
  margin-bottom: 10px;
}

.results {
  min-height: 100px;
}

.result {
  padding: 13px 16px;
  margin-bottom: 10px;
}

.result-head {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 7px;
}

.result-type {
  font-size: 10px;
  padding: 1px 7px;
  border-radius: 2px;
  flex-shrink: 0;
}

.result-title {
  font-size: 13px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-score {
  margin-left: auto;
  font-size: 11px;
  color: var(--ink-4);
  flex-shrink: 0;
}

.result-body {
  font-size: 12px;
  color: var(--ink-2);
  line-height: 1.8;
}

.result-foot {
  font-size: 10px;
  color: var(--ink-4);
  margin-top: 7px;
}

.empty {
  padding: 46px 20px;
  text-align: center;
}

.empty-text {
  font-size: 13px;
  color: var(--ink-3);
}

.empty-sub {
  font-size: 11px;
  color: var(--ink-4);
  margin-top: 5px;
}
</style>
