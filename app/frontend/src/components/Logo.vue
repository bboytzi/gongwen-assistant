<template>
  <svg
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
defineProps({
  size: { type: [Number, String], default: 26 },
  color: { type: String, default: '#A63A2E' },
  lineColor: { type: String, default: '#FAF8F3' },
  label: { type: String, default: '天府数产' },
})
</script>
