<script setup>
defineProps({ label: String, value: [String, Number], note: String, tone: { type: String, default: 'green' } })
</script>
<template><div class="stat-card" :class="`tone-${tone}`"><span>{{ label }}</span><strong>{{ value }}</strong><small>{{ note }}</small></div></template>
