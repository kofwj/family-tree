<template>
  <el-card class="settings-card audit-center-card" shadow="never">
    <template #header>
      <div class="settings-header audit-center-header">
        <div>
          <strong>治理域四：审计中心</strong>
          <p>把高敏操作、治理分组与近期动作拆开呈现，更接近真正的审计台账。</p>
        </div>
        <div class="audit-header-badges">
          <el-tag type="danger" effect="dark">高敏 {{ highPriorityLogs.length }}</el-tag>
          <el-tag type="info">已筛出 {{ filteredAuditLogs.length }} 条</el-tag>
        </div>
      </div>
    </template>

    <div class="audit-summary-grid">
      <div class="audit-summary-item is-danger">
        <span>高敏治理动作</span>
        <strong>{{ highPriorityAuditCount }}</strong>
        <small>涉及结构、权限或关键配置调整</small>
      </div>
      <div class="audit-summary-item">
        <span>成员类操作</span>
        <strong>{{ memberAuditCount }}</strong>
        <small>族谱成员新增、编辑、删除等动作</small>
      </div>
      <div class="audit-summary-item">
        <span>系统治理动作</span>
        <strong>{{ systemAuditCount }}</strong>
        <small>设置、备份、恢复与系统维护</small>
      </div>
      <div class="audit-summary-item">
        <span>用户权限动作</span>
        <strong>{{ userAuditCount }}</strong>
        <small>账号启停、密码重置、权限变更</small>
      </div>
    </div>

    <div class="audit-filter-bar">
      <div class="audit-filter-bar__left">
        <el-select v-model="localActionFilter" size="small" style="width: 164px">
          <el-option label="全部治理域" value="all" />
          <el-option label="成员治理" value="member" />
          <el-option label="系统治理" value="system" />
          <el-option label="用户权限" value="user" />
        </el-select>
        <el-switch v-model="localHighOnly" active-text="仅高敏" inactive-text="全部记录" />
      </div>
      <div class="audit-filter-bar__right">
        <span class="audit-filter-bar__meta">共 {{ filteredAuditLogs.length }} 条可见记录</span>
        <el-button v-if="filteredAuditLogs.length > collapsedLimit" text type="primary" @click="localExpanded = !localExpanded">
          {{ localExpanded ? `收起为前 ${collapsedLimit} 条` : `展开全部 ${filteredAuditLogs.length} 条` }}
        </el-button>
      </div>
    </div>

    <div v-if="highPriorityLogs.length" class="audit-focus-panel">
      <div class="audit-block-title">
        <div>
          <b>高敏操作置顶</b>
          <p>优先查看可能影响结构、权限与数据安全的治理动作。</p>
        </div>
      </div>
      <div class="audit-focus-list">
        <article v-for="row in highPriorityLogs" :key="`high-${row.id || row.createdAt || row.action}`" class="audit-focus-item">
          <div class="audit-focus-item__meta">
            <el-tag :type="auditTagType(row)">{{ auditActionLabel(row.action) }}</el-tag>
            <span>{{ auditTargetLabel(row) }}</span>
          </div>
          <p class="audit-focus-item__detail">{{ auditDetailText(row) }}</p>
          <div class="audit-focus-item__footer">
            <span>{{ row.actorUsername || '系统' }}</span>
            <span>{{ formatTime(row.createdAt) }}</span>
          </div>
        </article>
      </div>
    </div>

    <div v-if="groupedSections.length" class="audit-groups-shell">
      <div class="audit-group-stack">
      <section v-for="section in groupedSections" :key="section.key" class="audit-group-card">
        <div class="audit-block-title">
          <div>
            <b>{{ section.title }}</b>
            <p>{{ section.description }}</p>
          </div>
          <el-tag type="info">{{ section.logs.length }} 条</el-tag>
        </div>

        <div class="audit-timeline">
          <article v-for="row in section.logs" :key="`${section.key}-${row.id || row.createdAt || row.action}`" class="audit-timeline-item">
            <div class="audit-timeline-item__dot"></div>
            <div class="audit-timeline-item__content">
              <div class="audit-timeline-item__head">
                <div class="audit-timeline-item__labels">
                  <el-tag :type="auditTagType(row)" size="small">{{ auditActionLabel(row.action) }}</el-tag>
                  <span class="audit-target-pill">{{ auditTargetLabel(row) }}</span>
                  <span v-if="auditPriorityLabel(row)" class="audit-priority-pill">{{ auditPriorityLabel(row) }}</span>
                </div>
                <time>{{ formatTime(row.createdAt) }}</time>
              </div>
              <p class="audit-timeline-item__detail">{{ auditDetailText(row) }}</p>
              <div class="audit-timeline-item__foot">
                <span>操作人：{{ row.actorUsername || '系统' }}</span>
                <span>治理域：{{ section.title }}</span>
              </div>
            </div>
          </article>
        </div>
      </section>
      </div>
    </div>

    <el-empty v-else description="暂无可展示的审计记录，后续治理动作将在此沉淀。" />
  </el-card>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  auditLogs: { type: Array, default: () => [] },
  highPriorityAuditCount: { type: Number, default: 0 },
  memberAuditCount: { type: Number, default: 0 },
  formatTime: { type: Function, required: true },
  auditActionLabel: { type: Function, required: true },
  auditTargetLabel: { type: Function, required: true },
  auditPriorityLabel: { type: Function, required: true },
  auditTagType: { type: Function, required: true },
  auditDetailText: { type: Function, required: true },
})

const localActionFilter = ref('all')
const localHighOnly = ref(false)
const localExpanded = ref(false)
const collapsedLimit = 12

function classifyAudit(row) {
  const action = String(row?.action || '')
  if (action.startsWith('member.')) {
    return {
      key: 'member',
      title: '成员治理',
      description: '围绕族谱成员资料、关系结构与档案维护的变更。',
    }
  }
  if (action.startsWith('user.') || action.startsWith('auth.')) {
    return {
      key: 'user',
      title: '用户权限',
      description: '围绕账号启停、角色调整、密码与登录行为的治理记录。',
    }
  }
  return {
    key: 'system',
    title: '系统治理',
    description: '围绕系统设置、数据备份、恢复与运维动作的治理记录。',
  }
}

const filteredAuditLogs = computed(() => {
  return (props.auditLogs || []).filter((row) => {
    const section = classifyAudit(row).key
    if (localActionFilter.value !== 'all' && section !== localActionFilter.value) return false
    if (localHighOnly.value && row?.detail?.auditPriority !== 'high') return false
    return true
  }).slice(0, 24)
})

const visibleAuditLogs = computed(() => {
  return localExpanded.value ? filteredAuditLogs.value : filteredAuditLogs.value.slice(0, collapsedLimit)
})

const highPriorityLogs = computed(() => {
  return filteredAuditLogs.value.filter((row) => row?.detail?.auditPriority === 'high').slice(0, 4)
})

const groupedSections = computed(() => {
  const buckets = [
    { key: 'member', title: '成员治理', description: '围绕族谱成员资料、关系结构与档案维护的变更。', logs: [] },
    { key: 'user', title: '用户权限', description: '围绕账号启停、角色调整、密码与登录行为的治理记录。', logs: [] },
    { key: 'system', title: '系统治理', description: '围绕系统设置、数据备份、恢复与运维动作的治理记录。', logs: [] },
  ]
  for (const row of visibleAuditLogs.value) {
    const key = classifyAudit(row).key
    const bucket = buckets.find((item) => item.key === key)
    if (bucket) bucket.logs.push(row)
  }
  return buckets.filter((item) => item.logs.length)
})

const systemAuditCount = computed(() => {
  return (props.auditLogs || []).filter((row) => classifyAudit(row).key === 'system').length
})

const userAuditCount = computed(() => {
  return (props.auditLogs || []).filter((row) => classifyAudit(row).key === 'user').length
})
</script>

<style scoped>
.audit-center-header {
  align-items: flex-start;
  gap: 12px;
}

.audit-header-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.audit-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.audit-summary-item {
  padding: 14px 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(252, 248, 241, 0.95), rgba(245, 238, 226, 0.86));
  border: 1px solid rgba(190, 162, 127, 0.22);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.audit-summary-item.is-danger {
  background: linear-gradient(180deg, rgba(113, 31, 31, 0.08), rgba(184, 62, 36, 0.1));
  border-color: rgba(184, 62, 36, 0.2);
}

.audit-summary-item span {
  font-size: 12px;
  color: #8b7154;
}

.audit-summary-item strong {
  font-size: 24px;
  line-height: 1;
  color: #6a4726;
}

.audit-summary-item small {
  color: #9a8369;
  line-height: 1.5;
}

.audit-filter-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(249, 244, 234, 0.85);
  border: 1px solid rgba(190, 162, 127, 0.2);
  margin-bottom: 16px;
}

.audit-filter-bar__left {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.audit-filter-bar__right {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.audit-filter-bar__meta {
  font-size: 12px;
  color: #8b7154;
}

.audit-focus-panel,
.audit-group-card {
  border-radius: 20px;
  border: 1px solid rgba(190, 162, 127, 0.22);
  background: rgba(255, 251, 244, 0.95);
}

.audit-focus-panel {
  padding: 16px;
  margin-bottom: 16px;
  background: linear-gradient(180deg, rgba(255, 249, 244, 0.98), rgba(252, 242, 235, 0.96));
}

.audit-block-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.audit-block-title b {
  display: block;
  color: #5f4024;
  margin-bottom: 4px;
}

.audit-block-title p {
  margin: 0;
  color: #8c755d;
  font-size: 12px;
  line-height: 1.6;
}

.audit-focus-list,
.audit-group-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.audit-groups-shell {
  max-height: 620px;
  overflow: auto;
  padding-right: 4px;
}

.audit-focus-item {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(184, 62, 36, 0.16);
  background: rgba(255, 255, 255, 0.72);
}

.audit-focus-item__meta,
.audit-focus-item__footer,
.audit-timeline-item__head,
.audit-timeline-item__foot {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.audit-focus-item__meta span,
.audit-focus-item__footer span,
.audit-timeline-item__foot span,
.audit-timeline-item__head time {
  color: #8b7154;
  font-size: 12px;
}

.audit-focus-item__detail,
.audit-timeline-item__detail {
  margin: 10px 0;
  color: #5d4732;
  line-height: 1.75;
}

.audit-group-card {
  padding: 16px;
}

.audit-timeline {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 18px;
}

.audit-timeline::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 6px;
  bottom: 6px;
  width: 1px;
  background: linear-gradient(180deg, rgba(183, 152, 117, 0.35), rgba(183, 152, 117, 0.08));
}

.audit-timeline-item {
  position: relative;
}

.audit-timeline-item__dot {
  position: absolute;
  left: -18px;
  top: 12px;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #a06d39;
  box-shadow: 0 0 0 4px rgba(160, 109, 57, 0.12);
}

.audit-timeline-item__content {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(250, 246, 238, 0.78);
  border: 1px solid rgba(190, 162, 127, 0.16);
}

.audit-timeline-item__labels {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.audit-target-pill,
.audit-priority-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
}

.audit-target-pill {
  background: rgba(107, 79, 48, 0.08);
  color: #6c5032;
}

.audit-priority-pill {
  background: rgba(184, 62, 36, 0.12);
  color: #9f3821;
}

@media (max-width: 960px) {
  .audit-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
