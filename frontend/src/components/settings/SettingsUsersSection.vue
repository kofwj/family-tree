<template>
  <el-card v-if="canViewUsers" class="settings-card user-card" shadow="never">
    <template #header>
      <div class="settings-header">
        <div>
          <strong>治理域三：用户与权限</strong>
          <p>按角色分组管理账号，并把长列表收敛进更紧凑的治理面板。</p>
        </div>
        <el-button v-if="canCreateUser" type="primary" size="small" @click="$emit('open-user-dialog')">+ 新增用户</el-button>
      </div>
    </template>

    <div class="user-overview-grid">
      <div class="user-overview-card">
        <span>账号总数</span>
        <strong>{{ users.length }}</strong>
      </div>
      <div class="user-overview-card">
        <span>启用账号</span>
        <strong>{{ activeUsers.length }}</strong>
      </div>
      <div class="user-overview-card">
        <span>停用账号</span>
        <strong>{{ inactiveUsers.length }}</strong>
      </div>
      <div class="user-overview-card">
        <span>已绑定成员</span>
        <strong>{{ boundUsers.length }}</strong>
      </div>
    </div>

    <div class="user-toolbar">
      <el-input
        v-model="keyword"
        clearable
        size="small"
        class="user-search"
        placeholder="搜索用户名、显示名或绑定成员"
      />
      <div class="user-toolbar__right">
        <el-segmented v-model="statusFilter" size="small" :options="statusOptions" />
        <span class="user-toolbar__meta">筛出 {{ filteredUsers.length }} 个账号</span>
      </div>
    </div>

    <div v-loading="userLoading" class="user-list-shell">
      <div v-if="groupedUsers.length" class="user-group-scroll">
        <section v-for="group in groupedUsers" :key="group.key" class="user-role-group">
          <div class="user-role-group__header">
            <div>
              <strong>{{ group.label }}</strong>
              <p>{{ group.description }}</p>
            </div>
            <div class="user-role-group__badges">
              <span class="user-role-count">{{ group.total }} 人</span>
              <el-button v-if="group.total > collapsedLimit" text type="primary" @click="toggleGroup(group.key)">
                {{ expandedGroups[group.key] ? `收起为前 ${collapsedLimit} 人` : `查看更多 ${group.total} 人` }}
              </el-button>
            </div>
          </div>

          <div class="user-role-list">
            <article v-for="row in group.visibleUsers" :key="row.id" class="user-list-item compact">
              <div class="user-list-item__main">
                <div class="user-list-item__title-row">
                  <strong>{{ row.displayName || row.username }}</strong>
                  <el-tag size="small">{{ row.roleLabel || roleLabel(row.role) }}</el-tag>
                  <el-tag size="small" :type="row.isActive ? 'success' : 'danger'">{{ row.isActive ? '启用' : '停用' }}</el-tag>
                </div>
                <div class="user-list-item__subline">
                  <span>@{{ row.username }}</span>
                  <span>绑定：{{ memberName(row.memberId) }}</span>
                  <span>最近登录：{{ formatTime(row.lastLoginAt) }}</span>
                </div>
                <div class="user-list-item__scope">{{ scopeHint(row.role, row.memberId) }}</div>
              </div>

              <div class="user-list-item__actions compact-actions">
                <el-button v-if="canEditUser" size="small" @click="$emit('edit-user', row)">编辑</el-button>
                <el-button v-if="canResetPassword" size="small" @click="$emit('reset-password', row)">重置密码</el-button>
                <el-button
                  v-if="canDisableUser && row.id !== currentUser?.id"
                  size="small"
                  :type="row.isActive ? 'danger' : 'success'"
                  plain
                  @click="$emit('toggle-user-active', row)"
                >{{ row.isActive ? '停用' : '启用' }}</el-button>
              </div>
            </article>
          </div>
        </section>
      </div>

      <el-empty v-else description="暂无符合条件的用户" />
    </div>
  </el-card>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  users: { type: Array, default: () => [] },
  userLoading: { type: Boolean, default: false },
  currentUser: { type: Object, default: null },
  canViewUsers: { type: Boolean, default: false },
  canCreateUser: { type: Boolean, default: false },
  canEditUser: { type: Boolean, default: false },
  canDisableUser: { type: Boolean, default: false },
  canResetPassword: { type: Boolean, default: false },
  roleLabel: { type: Function, required: true },
  formatTime: { type: Function, required: true },
  memberName: { type: Function, required: true },
  scopeHint: { type: Function, required: true },
})

defineEmits(['open-user-dialog', 'edit-user', 'reset-password', 'toggle-user-active'])

const keyword = ref('')
const statusFilter = ref('all')
const collapsedLimit = 4
const expandedGroups = reactive({})
const statusOptions = [
  { label: '全部', value: 'all' },
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
]

const roleMeta = {
  super_admin: { key: 'super_admin', label: '超级管理员', description: '负责全局治理、权限控制与系统配置。' },
  admin: { key: 'admin', label: '管理员', description: '负责成员维护、备份与常规运营。' },
  editor: { key: 'editor', label: '编辑者', description: '负责资料录入、整理与分支维护。' },
  viewer: { key: 'viewer', label: '只读成员', description: '用于分支查阅、核对与轻量访问。' },
}

function toggleGroup(key) {
  expandedGroups[key] = !expandedGroups[key]
}

const activeUsers = computed(() => (props.users || []).filter(row => row?.isActive !== false))
const inactiveUsers = computed(() => (props.users || []).filter(row => row?.isActive === false))
const boundUsers = computed(() => (props.users || []).filter(row => !!row?.memberId))

const filteredUsers = computed(() => {
  const q = String(keyword.value || '').trim().toLowerCase()
  return (props.users || []).filter(row => {
    if (statusFilter.value === 'active' && row?.isActive === false) return false
    if (statusFilter.value === 'inactive' && row?.isActive !== false) return false
    if (!q) return true
    const haystack = [
      row?.username,
      row?.displayName,
      props.memberName(row?.memberId),
      props.roleLabel(row?.role),
    ].join(' ').toLowerCase()
    return haystack.includes(q)
  })
})

const groupedUsers = computed(() => {
  const buckets = Object.values(roleMeta).map(meta => ({ ...meta, users: [] }))
  for (const row of filteredUsers.value) {
    const key = roleMeta[row?.role]?.key || 'viewer'
    const bucket = buckets.find(item => item.key === key)
    if (bucket) bucket.users.push(row)
  }
  return buckets
    .map(bucket => ({
      ...bucket,
      total: bucket.users.length,
      visibleUsers: expandedGroups[bucket.key] ? bucket.users : bucket.users.slice(0, collapsedLimit),
    }))
    .filter(bucket => bucket.total > 0)
})
</script>

<style scoped>
.user-overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.user-overview-card {
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(255,255,255,.72);
  border: 1px solid rgba(190, 162, 127, 0.2);
}

.user-overview-card span {
  display: block;
  font-size: 12px;
  color: #8b7154;
  margin-bottom: 4px;
}

.user-overview-card strong {
  display: block;
  font-size: 22px;
  color: #6a4726;
}

.user-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.user-toolbar__right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.user-toolbar__meta {
  font-size: 12px;
  color: #8b7154;
}

.user-search {
  width: min(320px, 100%);
}

.user-list-shell {
  min-height: 120px;
}

.user-group-scroll {
  max-height: 700px;
  overflow: auto;
  padding-right: 4px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.user-role-group {
  border-radius: 18px;
  border: 1px solid rgba(190, 162, 127, 0.18);
  background: rgba(255,255,255,.52);
  padding: 14px;
}

.user-role-group__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 12px;
}

.user-role-group__header strong {
  color: #5f4024;
}

.user-role-group__header p {
  margin: 4px 0 0;
  color: #8b7154;
  font-size: 12px;
  line-height: 1.6;
}

.user-role-group__badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.user-role-count {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(107, 79, 48, 0.08);
  color: #6c5032;
  font-size: 12px;
}

.user-role-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.user-list-item.compact {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(190, 162, 127, 0.16);
  background: rgba(250,246,238,.82);
}

.user-list-item__main {
  flex: 1;
  min-width: 0;
}

.user-list-item__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.user-list-item__subline {
  margin-top: 6px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: #8b7154;
  font-size: 12px;
}

.user-list-item__scope {
  margin-top: 8px;
  color: #5f4228;
  font-size: 13px;
  line-height: 1.65;
}

.user-list-item__actions.compact-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

@media (max-width: 1100px) {
  .user-overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .user-list-item.compact,
  .user-role-group__header {
    flex-direction: column;
  }

  .user-list-item__actions.compact-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 700px) {
  .user-overview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
