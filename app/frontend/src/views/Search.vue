<template>
  <div style="padding: 24px;">
    <div style="margin-bottom: 24px;">
      <h2 style="margin: 0; font-size: 18px;">检索中心</h2>
    </div>
    <el-row :gutter="20">
      <el-col :span="5">
        <el-card shadow="never">
          <div style="font-weight: 600; margin-bottom: 12px; font-size: 13px;">检索范围</div>
          <el-checkbox-group v-model="filters.kb_ids" style="display: flex; flex-direction: column; gap: 6px;">
            <el-checkbox v-for="kb in companyKbs" :key="kb.id" :label="kb.id">{{ kb.name }}</el-checkbox>
            <el-checkbox v-for="kb in personalKbs" :key="kb.id" :label="kb.id">{{ kb.name }}</el-checkbox>
          </el-checkbox-group>
          <el-divider />
          <div style="font-weight: 600; margin-bottom: 8px; font-size: 13px;">文档类型</div>
          <el-checkbox-group v-model="filters.doc_types" style="display: flex; flex-direction: column; gap: 6px;">
            <el-checkbox label="regulation">管理办法</el-checkbox>
            <el-checkbox label="case">请示材料</el-checkbox>
            <el-checkbox label="template">模板</el-checkbox>
          </el-checkbox-group>
          <el-divider />
          <div style="font-weight: 600; margin-bottom: 8px; font-size: 13px;">请示类型</div>
          <el-checkbox-group v-model="filters.doc_categories" style="display: flex; flex-direction: column; gap: 6px;">
            <el-checkbox label="procurement">采购类</el-checkbox>
            <el-checkbox label="personnel">人事类</el-checkbox>
            <el-checkbox label="fund">资金类</el-checkbox>
            <el-checkbox label="project">项目类</el-checkbox>
          </el-checkbox-group>
        </el-card>
      </el-col>
      <el-col :span="19">
        <el-card shadow="never">
          <div style="display: flex; gap: 8px; margin-bottom: 16px;">
            <el-radio-group v-model="mode" style="margin-bottom: 0;">
              <el-radio-button label="hybrid">语义检索</el-radio-button>
              <el-radio-button label="keyword">关键词检索</el-radio-button>
            </el-radio-group>
            <el-input v-model="query" placeholder="输入自然语言描述或关键词" style="flex: 1;" @keyup.enter="handleSearch">
              <template #append>
                <el-button @click="handleSearch" :loading="searching">检索</el-button>
              </template>
            </el-input>
          </div>
          <div v-if="results.length > 0" style="font-size: 13px; color: #888; margin-bottom: 12px;">
            找到 {{ results.length }} 条结果 · 耗时 {{ elapsed }}ms
          </div>
          <div v-for="(r, i) in results" :key="i" style="padding: 12px 0; border-bottom: 1px solid #f0f0f0;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
              <div>
                <el-tag size="small" :type="r.doc_type === 'regulation' ? 'primary' : 'success'" style="margin-right: 8px;">
                  {{ r.doc_type === 'regulation' ? '管理办法' : '历史请示' }}
                </el-tag>
                <span style="font-weight: 500; font-size: 14px;">{{ r.title }}</span>
              </div>
              <span style="font-size: 12px; color: #888;">相关度 {{ Math.round(r.score * 100) }}%</span>
            </div>
            <div style="font-size: 13px; color: #666; margin-top: 6px; line-height: 1.6;">
              {{ r.content.substring(0, 150) }}...
            </div>
            <div style="font-size: 12px; color: #aaa; margin-top: 4px;">
              <span>{{ r.source }}</span>
            </div>
          </div>
          <div v-if="searched && results.length === 0" style="text-align: center; padding: 40px; color: #888;">
            未找到相关结果
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
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
const filters = ref({
  kb_ids: [],
  doc_types: [],
  doc_categories: [],
})

onMounted(async () => {
  const data = await api.get('/kb/bases')
  companyKbs.value = data.company
  personalKbs.value = data.personal
  // Default: check all
  filters.value.kb_ids = [...companyKbs.value.map(k => k.id), ...personalKbs.value.map(k => k.id)]
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
      doc_categories: filters.value.doc_categories,
      limit: 20,
    })
    results.value = data.results
    elapsed.value = data.elapsed_ms
  } finally {
    searching.value = false
  }
}
</script>
