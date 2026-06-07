<template>
  <div>
    <div class="archive-header">
      <div>
        <el-tag>叁 · 族谱备份</el-tag>
        <p class="archive-tip">自动备份仅保留最近 30 个；手动备份、恢复前保护备份不会被自动清理。</p>
      </div>
      <div class="archive-summary">
        <el-tag type="info">总数 {{ backups.length }}</el-tag>
        <el-tag type="success">手动 {{ manualCount }}</el-tag>
        <el-tag type="warning">自动 {{ autoCount }}</el-tag>
      </div>
    </div>

    <el-table :data="backups" empty-text="暂无备份">
      <el-table-column prop="file" label="备份文件" min-width="270" show-overflow-tooltip />
      <el-table-column label="类型" width="135">
        <template #default="{ row }">
          <el-tag :type="tagType(row.backupType)" effect="plain">{{ row.typeLabel || fallbackTypeLabel(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="来源" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.source || row.reason || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="时间" width="180">
        <template #default="{ row }">
          {{ formatTime(row.createdAt || row.mtime) }}
        </template>
      </el-table-column>
      <el-table-column label="大小" width="95">
        <template #default="{ row }">
          {{ formatSize(row.size) }}
        </template>
      </el-table-column>
      <el-table-column label="是否可删除" width="130" align="center">
        <template #default="{ row }">
          <el-tooltip :content="row.deleteHint || '可手动删除'" placement="top">
            <el-tag :type="row.canDelete === false ? 'info' : 'danger'" effect="plain">
              {{ row.canDelete === false ? '不可删' : '可删除' }}
            </el-tag>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canDownload" link type="primary" size="small" @click="$emit('download-backup', row)">下载</el-button>
          <el-button v-if="canRestore" link type="warning" size="small" @click="$emit('restore-backup', row)">恢复</el-button>
          <el-button v-if="canDelete && row.canDelete !== false" link type="danger" size="small" @click="$emit('delete-backup', row)">删除</el-button>
          <span v-if="!canDownload && !canRestore && !canDelete">无操作权限</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  backups: { type: Array, default: () => [] },
  canDownload: { type: Boolean, default: false },
  canRestore: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
})

function tagType(type) {
  if (type === 'manual') return 'success'
  if (type === 'safety') return 'danger'
  return 'warning'
}

function fallbackTypeLabel(row) {
  if (row?.isManual) return '手动备份'
  if (row?.isSafety) return '恢复前保护备份'
  return '自动备份'
}

function formatTime(value) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatSize(bytes) {
  const n = Number(bytes || 0)
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

const manualCount = computed(() => props.backups.filter(b => b.backupType === 'manual' || b.isManual).length)
const autoCount = computed(() => props.backups.filter(b => b.backupType === 'auto' || b.isAuto).length)

defineEmits(['download-backup', 'restore-backup', 'delete-backup'])
</script>

<style scoped>
.archive-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.archive-tip {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.archive-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
