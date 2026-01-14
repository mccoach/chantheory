// src/constants/afterHoursBulk.js
// ==============================
// 盘后批量入队（/api/ensure-data/bulk）契约参考手册（前端用）
// - 单一真相源：purpose / max_jobs 默认兜底 / status 与 reason 展示映射
// - 后端 MVP 只承诺 accepted/rejected；其它枚举仅作前端展示兜底（不作为逻辑依赖）
// ==============================

// ===== 契约定稿：固定用途 =====
export const AFTER_HOURS_PURPOSE = "after_hours";

// ===== 单次 bulk 最大 job 数（后端响应也会回传 max_jobs；这里是前端兜底值）=====
export const AFTER_HOURS_BULK_MAX_JOBS_DEFAULT = 30000;

// ===== Bulk items[].status（入队层）=====
export const BULK_ITEM_STATUS = {
  ACCEPTED: "accepted",
  REJECTED: "rejected",

  // 可选扩展（后端未来可能给）：前端仅兜底展示，不做强依赖
  DUPLICATE: "duplicate",
  SKIPPED: "skipped",
};

// ===== Bulk items[].reason 建议 code（入队层原因）=====
export const BULK_REASON_CODES = {
  // 参数/校验类（前端可修复）
  MISSING_FIELD: "missing_field",
  INVALID_FIELD: "invalid_field",
  INVALID_JOB_ID: "invalid_job_id",
  DUPLICATE_JOB_ID: "duplicate_job_id",
  JOB_ID_TOO_LONG: "job_id_too_long",
  INVALID_PARAMS: "invalid_params",

  // 批次限制类（前端可分片/降载）
  TOO_MANY_JOBS: "too_many_jobs",
  PAYLOAD_TOO_LARGE: "payload_too_large",
  BATCH_REJECTED: "batch_rejected",

  // 限流/拥堵类
  RATE_LIMITED: "rate_limited",
  QUEUE_OVERLOADED: "queue_overloaded",

  // 权限/认证类
  UNAUTHORIZED: "unauthorized",
  FORBIDDEN: "forbidden",

  // 幂等/重复提交类（可选）
  DUPLICATE_REQUEST: "duplicate_request",

  // 后端内部类
  INTERNAL_ERROR: "internal_error",
  ENQUEUE_FAILED: "enqueue_failed",
  UNKNOWN_ERROR: "unknown_error",
};

// ===== Bulk reason code 的中文说明（用于 UI 展示）=====
export const BULK_REASON_LABELS_ZH = {
  [BULK_REASON_CODES.MISSING_FIELD]: "缺少必填字段",
  [BULK_REASON_CODES.INVALID_FIELD]: "字段值非法",
  [BULK_REASON_CODES.INVALID_JOB_ID]: "job_id 非法",
  [BULK_REASON_CODES.DUPLICATE_JOB_ID]: "job_id 重复（批次内必须唯一）",
  [BULK_REASON_CODES.JOB_ID_TOO_LONG]: "job_id 过长",
  [BULK_REASON_CODES.INVALID_PARAMS]: "params 参数非法",

  [BULK_REASON_CODES.TOO_MANY_JOBS]: "任务数量超过后端限制（请分批提交）",
  [BULK_REASON_CODES.PAYLOAD_TOO_LARGE]: "请求体过大（请分批提交）",
  [BULK_REASON_CODES.BATCH_REJECTED]: "整批被拒绝（请稍后重试）",

  [BULK_REASON_CODES.RATE_LIMITED]: "后端限流（请稍后重试）",
  [BULK_REASON_CODES.QUEUE_OVERLOADED]: "队列拥堵（请稍后重试）",

  [BULK_REASON_CODES.UNAUTHORIZED]: "未认证或认证已失效",
  [BULK_REASON_CODES.FORBIDDEN]: "无权限提交该任务",

  [BULK_REASON_CODES.DUPLICATE_REQUEST]: "重复提交（可能已提交成功）",

  [BULK_REASON_CODES.INTERNAL_ERROR]: "后端内部错误",
  [BULK_REASON_CODES.ENQUEUE_FAILED]: "入队失败",
  [BULK_REASON_CODES.UNKNOWN_ERROR]: "未知错误",
};

// ===== SSE task_done overall_status（执行层结果）=====
export const TASK_DONE_STATUS = {
  SUCCESS: "success",
  FAILED: "failed",
  CANCELED: "canceled",
  PARTIAL_SUCCESS: "partial_success",
};
