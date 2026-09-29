export const formatDuration = value => { const total=Math.max(0,Math.round(Number(value)||0)); return `${Math.floor(total/60)}:${String(total%60).padStart(2,'0')}` }
