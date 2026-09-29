<script setup>
import { computed } from 'vue'
import BaseChart from './BaseChart.vue'
const props = defineProps({ segments: { type: Array, default: () => [] } })
const colors = { standing: '#22c55e', walking: '#38bdf8', sitting: '#f59e0b', unknown: '#64748b' }
const option = computed(() => ({
  tooltip: { formatter: p => `${p.data.name}<br>${p.data.value[0]}s - ${p.data.value[1]}s` },
  grid: { left: 20, right: 20, top: 28, bottom: 36 }, xAxis: { type: 'value', name: '秒' }, yAxis: { type: 'category', data: ['行为'] },
  series: [{ type: 'custom', renderItem(params, api) { const s=api.coord([api.value(0),0]); const e=api.coord([api.value(1),0]); return { type:'rect', shape:{x:s[0],y:s[1]-18,width:Math.max(2,e[0]-s[0]),height:36}, style:api.style() } },
    data: props.segments.map(x => ({ name:x.action, value:[x.start_time,x.end_time], itemStyle:{color:colors[x.action]||colors.unknown} })) }]
}))
</script>
<template><BaseChart :option="option" height="230px" /></template>
