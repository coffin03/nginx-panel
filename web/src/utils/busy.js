// loading 至少保持可见一段时间，避免本地请求过快时用户感受不到反馈
const MIN_VISIBLE_MS = 400

export async function holdLoading(startedAt, ms = MIN_VISIBLE_MS) {
  const remain = ms - (Date.now() - startedAt)
  if (remain > 0) await new Promise((resolve) => setTimeout(resolve, remain))
}