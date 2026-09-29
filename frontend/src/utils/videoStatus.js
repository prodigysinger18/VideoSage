export const videoStatusLabel = status => ({
  pending: '待分析',
  queued: '排队中',
  analyzing: '分析中',
  importing: '入库中',
  completed: '已完成',
  failed: '失败',
  uploaded_pending_analysis: '待分析'
})[status] || '待分析'

export const videoStatusType = status => ({
  completed: 'success',
  failed: 'danger',
  analyzing: 'primary',
  importing: 'primary'
})[status] || 'warning'
