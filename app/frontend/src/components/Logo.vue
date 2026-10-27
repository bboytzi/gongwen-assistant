<template>
  <img
    v-if="customSrc"
    :src="customSrc"
    :width="size"
    :height="size"
    :alt="label"
    class="logo-img"
  />
  <svg
    v-else
    :width="size"
    :height="size"
    viewBox="0 0 88 88"
    role="img"
    :aria-label="label"
    style="display: block; flex-shrink: 0;"
  >
    <rect x="4" y="4" width="80" height="80" rx="5" :fill="color" />
    <rect x="23" y="24" width="8" height="40" :fill="lineColor" />
    <rect x="40" y="24" width="8" height="40" :fill="lineColor" />
    <rect x="57" y="24" width="8" height="11" :fill="lineColor" />
    <rect x="57" y="39" width="8" height="11" :fill="lineColor" />
    <rect x="57" y="54" width="8" height="10" :fill="lineColor" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'
import { useSystemStore } from '../store/system'

const props = defineProps({
  size: { type: [Number, String], default: 26 },
  color: { type: String, default: '#A63A2E' },
  lineColor: { type: String, default: '#FAF8F3' },
  label: { type: String, default: '系统标识' },
})

const system = useSystemStore()

// 管理员上传过 logo 就用它，否则回落到内置方印
const customSrc = computed(() => system.logo || null)
</script>

<style scoped>
.logo-img {
  display: block;
  flex-shrink: 0;
  border-radius: 4px;
  object-fit: contain;
}
</style>
