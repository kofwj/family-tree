<template>
  <div class="workspace workspace--topbar">
    <main class="content-panel" v-loading="loading">
      <div class="workspace-topbar">
        <div class="workspace-topbar__brand">
          <div class="workspace-topbar__crest">{{ familyCrest }}</div>
          <div class="workspace-topbar__text">
            <div class="workspace-topbar__eyebrow">Genealogy Workspace</div>
            <div class="workspace-topbar__title">{{ settings.siteTitle }}</div>
            <div class="workspace-topbar__desc">{{ settings.subtitle }}</div>
          </div>
        </div>

        <div class="workspace-topbar__meta">
          <div class="meta-card meta-card--primary" v-if="families.length > 0">
            <div class="meta-card__icon">
              <el-icon><OfficeBuilding /></el-icon>
            </div>
            <div class="meta-card__content">
              <span class="meta-card__label">当前家族</span>
              <el-select 
                v-model="currentFamilyId" 
                @change="switchFamily" 
                size="small"
                class="meta-card__select"
              >
                <el-option
                  v-for="family in families"
                  :key="family.id"
                  :label="family.name"
                  :value="family.id"
                >
                  <span>{{ family.name }}</span>
                  <el-tag v-if="family.isPrimary" type="success" size="small" style="margin-left: 8px">主</el-tag>
                </el-option>
              </el-select>
            </div>
          </div>
          
          <div class="meta-card">
            <div class="meta-card__icon">
              <el-icon><View /></el-icon>
            </div>
            <div class="meta-card__content">
              <span class="meta-card__label">当前视图</span>
              <strong class="meta-card__value">{{ currentSectionLabel }}</strong>
            </div>
          </div>
          
          <div class="meta-card">
            <div class="meta-card__icon">
              <el-icon><User /></el-icon>
            </div>
            <div class="meta-card__content">
              <span class="meta-card__label">当前角色</span>
              <strong class="meta-card__value">{{ roleLabel }}</strong>
            </div>
          </div>
          
          <div class="meta-card meta-card--stats">
            <div class="meta-card__icon">
              <el-icon><DataAnalysis /></el-icon>
            </div>
            <div class="meta-card__content">
              <span class="meta-card__label">数据统计</span>
              <div class="meta-card__stats">
                <div class="stat-item">
                  <span class="stat-value">{{ members.length }}</span>
                  <span class="stat-label">成员</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ generationCount }}</span>
                  <span class="stat-label">世代</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ tree.length }}</span>
                  <span class="stat-label">分支</span>
                </div>
                <div class="stat-item">
                  <span class="stat-value">{{ backups.length }}</span>
                  <span class="stat-label">备份</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="workspace-topbar__actions">
          <el-button type="primary" :icon="Refresh" @click="loadAll">刷新</el-button>
          <el-button :icon="Download" @click="downloadImportTemplate" v-if="can('member.import')">下载模板</el-button>
          <el-upload
            v-if="can('member.import')"
            :show-file-list="false"
            :auto-upload="false"
            accept=".xlsx,.xls"
            :on-change="uploadMemberExcel"
          >
            <el-button :icon="Upload">导入成员</el-button>
          </el-upload>
          <el-button type="warning" :icon="FolderOpened" @click="backup" v-if="can('backup.create')">手动备份</el-button>
          <el-button :icon="darkMode ? Sunny : Moon" @click="toggleTheme">
            {{ darkMode ? '浅色' : '深色' }}
          </el-button>
          <el-button type="danger" @click="logout">退出</el-button>
        </div>
      </div>

      <el-tabs v-model="tab" class="main-tabs">
        <el-tab-pane label="壹 · 家族世系" name="tree">
          <TreePanel
            :nodes="flowNodes"
            :edges="flowEdges"
            :tree="tree"
            :members="members"
            :active-member-id="activeTreeMemberId"
            @node-click="onFlowNodeClick"
            @toggle-branch="toggleTreeBranch"
            @expand-all="expandAllTreeBranches"
            @collapse-main-line="collapseTreeToMainLine"
            @expand-generation="expandTreeToGeneration"
            @reset-view="rebuildFlow"
          />
        </el-tab-pane>

        <el-tab-pane label="贰 · 成员录" name="members">
          <div style="margin-bottom:10px; display:flex; gap:10px; align-items:center">
            <el-button v-if="can('member.create')" type="primary" size="small" @click="openCreateForm">+ 新增成员</el-button>
            <el-tag type="info">当前角色：{{ currentUser.displayName }} / {{ roleLabel }}</el-tag>
          </div>
          <MembersPanel
            :members="members"
            :visible-fields="settings.memberVisibleFields"
            :can-edit="can('member.edit_profile')"
            :can-delete="can('member.delete')"
            :can-config-fields="can('settings.edit_display')"
            :families="families"
            @open-member="openMember"
            @edit-member="startEdit"
            @delete-member="confirmDelete"
            @update-visible-fields="updateMemberVisibleFields"
          />
        </el-tab-pane>

        <el-tab-pane v-if="can('backup.view')" label="叁 · 族谱备份" name="backup">
          <ArchivePanel
            :backups="backups"
            :can-download="can('backup.download')"
            :can-restore="can('backup.restore')"
            :can-delete="can('backup.delete')"
            @download-backup="downloadBackup"
            @restore-backup="restoreBackup"
            @delete-backup="deleteBackup"
            @upload-backup="uploadBackup"
          />
        </el-tab-pane>

        <el-tab-pane v-if="canOpenSettingsPanel" label="肆 · 系统治理" name="settings">
          <SettingsPanel
            :settings="settings"
            :saving="savingSettings"
            :readonly="!can('settings.edit_basic')"
            :users="users"
            :roles="roles"
            :members="members"
            :audit-logs="auditLogs"
            :quality-report="qualityReport"
            :review-requests="reviewRequests"
            :sources="sources"
            :families="families"
            :current-user="currentUser"
            :user-loading="userLoading"
            :can-view-users="can('user.view')"
            :can-create-user="can('user.create')"
            :can-edit-user="can('user.edit_role')"
            :can-disable-user="can('user.disable')"
            :can-reset-password="can('user.reset_password')"
            :can-view-settings="can('settings.view')"
            :can-view-quality="can('quality.view')"
            :can-view-review="can('review.view')"
            :can-approve-review="can('review.approve')"
            :can-view-sources="can('source.view')"
            :can-manage-sources="can('source.manage')"
            :can-export-gedcom="can('export.gedcom')"
            :can-view-audit="can('audit.view')"
            :can-manage-families="can('family.view')"
            :can-edit-families="can('family.edit')"
            @save-settings="saveSettings"
            @create-user="createUser"
            @update-user="updateUser"
            @toggle-user-active="toggleUserActive"
            @reset-user-password="resetUserPassword"
            @refresh-quality="loadQualityReport"
            @approve-review="approveReview"
            @reject-review="rejectReview"
            @create-source="createSource"
            @update-source="updateSource"
            @delete-source="deleteSource"
            @export-gedcom="exportGedcom"
            @save-family="saveFamily"
            @load-family-users="loadFamilyUsers"
            @add-family-user="addFamilyUser"
            @remove-family-user="removeFamilyUser"
          />
        </el-tab-pane>
      </el-tabs>
    </main>

    <MemberDrawer
      v-model="drawer"
      :member="selected"
      :all-members="members"
      :sources="sources"
      :citations="selectedCitations"
      :citation-loading="citationLoading"
      :can-edit="can('member.edit_profile') && selected?.visibilityScope !== 'basic'"
      :can-delete="can('member.delete') && selected?.visibilityScope !== 'basic'"
      :can-view-source="can('source.view') && selected?.visibilityScope !== 'basic'"
      :can-manage-sources="can('source.manage') && selected?.visibilityScope !== 'basic'"
      @open-member="openMember"
      @locate-member="locateMemberInTree"
      @upload-photo="uploadMemberPhoto"
      @edit-member="onDrawerEdit"
      @delete-member="onDrawerDelete"
      @refresh-citations="loadMemberCitations"
      @create-citation="createMemberCitation"
    />
    <MemberForm
      v-model="formVisible"
      :member="editingMember"
      :all-members="members"
      :saving="savingForm"
      :can-edit-core-relation="can('member.edit_core_relation')"
      @submit="onFormSubmit"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'
import { ElMessageBox } from 'element-plus/es/components/message-box/index'
import { Refresh, Download, Upload, FolderOpened, Sunny, Moon, OfficeBuilding, View, User, DataAnalysis } from '@element-plus/icons-vue'
import api from '../api/client'
import TreePanel from '../components/TreePanel.vue'
import MembersPanel from '../components/MembersPanel.vue'
import ArchivePanel from '../components/ArchivePanel.vue'
import MemberDrawer from '../components/MemberDrawer.vue'
import MemberForm from '../components/MemberForm.vue'
import SettingsPanel from '../components/SettingsPanel.vue'

const router = useRouter()
const members = ref([])
const tree = ref([])
const backups = ref([])
const users = ref([])
const roles = ref([])
const auditLogs = ref([])
const qualityReport = ref({ summary: { total: 0, bySeverity: {}, byCategory: {} }, issues: [] })
const reviewRequests = ref([])
const sources = ref([])
const selectedCitations = ref([])
const citationLoading = ref(false)
const userLoading = ref(false)
const currentUser = ref({ id: 0, username: '', displayName: '访客', role: 'viewer', capabilities: [], isActive: true, memberId: null })
const loading = ref(false)
const tab = ref('tree')
const drawer = ref(false)
const selected = ref(null)
const activeTreeMemberId = ref(null)
const darkMode = ref(localStorage.getItem('theme') === 'dark')
const savingSettings = ref(false)

// Family management
const families = ref([])
const currentFamily = ref(null)
const currentFamilyId = ref(null)

const settings = ref({
  siteTitle: '陈氏宗族家谱',
  familySurname: '陈',
  subtitle: '承先祖之德 · 启后世之贤',
  coverKicker: 'CHEN CLAN · GENEALOGY',
  treeDescription: '可阅读的大型关系结构 · 分层对齐 · 拖拽缩放',
  memberVisibleFields: [
    'name', 'gender', 'generation', 'generationName', 'rankTitle',
    'branch', 'birthDate', 'birthPlace', 'residence', 'spouseIds', 'fatherId', 'motherId'
  ],
  fieldVisibilityTemplates: { viewer: 'public', editor: 'archive' },
})

// form
const formVisible = ref(false)
const editingMember = ref(null)
const savingForm = ref(false)

const familyCrest = computed(() => (settings.value.familySurname || settings.value.siteTitle || '陈').slice(0, 1))
const roleLabel = computed(() => ({ super_admin: '超级管理员', admin: '管理员', editor: '编辑者', viewer: '只读成员' }[currentUser.value?.role] || currentUser.value?.role || '未登录'))
const currentSectionLabel = computed(() => ({ tree: '家族世系', members: '成员录', backup: '族谱备份', settings: '系统治理' }[tab.value] || '家族世系'))
const publicMemberCount = computed(() => (members.value || []).filter(item => item?.isPublic !== false).length)
const capabilityCount = computed(() => (currentUser.value?.capabilities || []).length)

function can(capability) {
  return (currentUser.value?.capabilities || []).includes(capability)
}

const canOpenSettingsPanel = computed(() => [
  'settings.view', 'quality.view', 'review.view', 'source.view', 'audit.view', 'user.view', 'export.gedcom',
].some(capability => can(capability)))

const generationCount = computed(() => {
  const set = new Set((members.value || []).map(m => m.generation).filter(Boolean))
  return set.size
})

const flowNodes = ref([])
const flowEdges = ref([])

const collapsedBranchIds = ref(new Set())
const mainLineIds = ref(new Set())
const branchPalette = ['#c59b6b', '#87a878', '#7f9dbd', '#b98389', '#b7a36a', '#8aa6a3', '#b48ead', '#9c8f7d']

function nodeKey(node) {
  return String(node?.id ?? node?.name ?? '')
}

function descendantCount(node) {
  let total = 0
  for (const child of (node?.children || [])) {
    total += 1 + descendantCount(child)
  }
  return total
}

function computeMainLine(roots) {
  const ids = new Set()
  function walk(node) {
    if (!node) return
    ids.add(nodeKey(node))
    const children = [...(node.children || [])]
      .sort((a, b) => (Number(a.rankNo || a.rank_no || 999) - Number(b.rankNo || b.rank_no || 999)) || String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN'))
    if (children.length) walk(children[0])
  }
  for (const root of (roots || [])) walk(root)
  return ids
}

function flattenTreeWithDagre(roots) {
  const visibleNodes = []
  const visibleEdges = []
  const generationMap = new Map()
  const branchFrames = new Map()
  const seen = new Set()
  const branchIndexByRootChild = new Map()
  const mainIds = computeMainLine(roots)
  mainLineIds.value = mainIds

  const normalizedRoots = [...(roots || [])]
    .sort((a, b) => (Number(a.generation || 999) - Number(b.generation || 999)) || String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN'))

  function getGeneration(node, depth) {
    return Number(node?.generation || node?.generationNo || depth || 1)
  }

  function getBranchInfo(node, root, topChild, rootIndex) {
    if (!topChild) {
      return { label: '主源', index: rootIndex % branchPalette.length, color: branchPalette[rootIndex % branchPalette.length] }
    }
    const key = nodeKey(topChild)
    if (!branchIndexByRootChild.has(key)) branchIndexByRootChild.set(key, branchIndexByRootChild.size)
    const index = branchIndexByRootChild.get(key)
    const label = topChild.branch || `${topChild.name || `${index + 1}房`}支`
    return { label, index, color: branchPalette[index % branchPalette.length] }
  }

  function walk(node, parent, depth, root, topChild, rootIndex) {
    const id = nodeKey(node)
    if (!id || seen.has(id)) return
    seen.add(id)

    const generation = getGeneration(node, depth)
    const children = [...(node.children || [])]
      .sort((a, b) => (Number(a.rankNo || a.rank_no || 999) - Number(b.rankNo || b.rank_no || 999)) || String(a.name || '').localeCompare(String(b.name || ''), 'zh-Hans-CN'))
    const hasChildren = children.length > 0
    const isCollapsed = collapsedBranchIds.value.has(id)
    const branchInfo = getBranchInfo(node, root, topChild, rootIndex)
    const spouseNames = (node.spouses || []).map(s => s.name).filter(Boolean).join('、')
    const isMainLine = mainIds.has(id)

    if (!generationMap.has(generation)) generationMap.set(generation, [])
    generationMap.get(generation).push({
      node,
      id,
      parentId: parent ? nodeKey(parent) : null,
      generation,
      branchInfo,
      isMainLine,
      hasChildren,
      childCount: children.length,
      descendantCount: descendantCount(node),
      isCollapsed,
      spouseNames,
    })

    if (parent) {
      visibleEdges.push({
        id: `e-${nodeKey(parent)}-${id}`,
        source: nodeKey(parent),
        target: id,
        type: 'smoothstep',
        animated: false,
        style: {
          stroke: isMainLine && mainIds.has(nodeKey(parent)) ? '#6d3f1f' : branchInfo.color,
          strokeWidth: isMainLine && mainIds.has(nodeKey(parent)) ? 4.2 : 2.25,
        },
        class: isMainLine && mainIds.has(nodeKey(parent)) ? 'lineage-edge-main' : 'lineage-edge-branch',
      })
    }

    if (isCollapsed) return
    children.forEach((child) => walk(child, node, generation + 1, root, topChild || child, rootIndex))
  }

  normalizedRoots.forEach((root, rootIndex) => walk(root, null, getGeneration(root, 1), root, null, rootIndex))

  const generations = [...generationMap.keys()].sort((a, b) => a - b)
  const columnGap = 330
  const rowGap = 178
  const branchGroupGap = 92
  const nodeW = 220
  const nodeH = 128
  const startX = 90
  const startY = 82

  const branchCountsByGeneration = new Map()
  for (const generation of generations) {
    const branchIndices = new Set((generationMap.get(generation) || []).map(item => item.branchInfo.index))
    branchCountsByGeneration.set(generation, branchIndices.size)
  }

  const ordered = []
  for (const generation of generations) {
    const rows = generationMap.get(generation) || []
    rows.sort((a, b) => {
      if (a.branchInfo.index !== b.branchInfo.index) return a.branchInfo.index - b.branchInfo.index
      if (a.isMainLine !== b.isMainLine) return a.isMainLine ? -1 : 1
      return String(a.node.name || '').localeCompare(String(b.node.name || ''), 'zh-Hans-CN')
    })
    let previousBranchIndex = null
    let branchOffset = 0
    rows.forEach((item, rowIndex) => {
      if (previousBranchIndex !== null && item.branchInfo.index !== previousBranchIndex) {
        branchOffset += branchGroupGap
      }
      previousBranchIndex = item.branchInfo.index
      const generationBranchCount = branchCountsByGeneration.get(generation) || 1
      const x = startX + (generation - generations[0]) * columnGap
      const y = startY + rowIndex * rowGap + branchOffset + (generationBranchCount > 1 ? item.branchInfo.index * 10 : 0)
      ordered.push({ ...item, x, y })
      const frame = branchFrames.get(item.branchInfo.label) || { color: item.branchInfo.color, minX: Infinity, maxX: -Infinity, minY: Infinity, maxY: -Infinity, label: item.branchInfo.label }
      frame.minX = Math.min(frame.minX, x - 28)
      frame.maxX = Math.max(frame.maxX, x + nodeW + 28)
      frame.minY = Math.min(frame.minY, y - 26)
      frame.maxY = Math.max(frame.maxY, y + nodeH + 26)
      branchFrames.set(item.branchInfo.label, frame)
    })
  }

  for (const frame of branchFrames.values()) {
    if (frame.label === '主源' || !Number.isFinite(frame.minX)) continue
    visibleNodes.push({
      id: `branch-frame-${frame.label}`,
      type: 'group',
      position: { x: frame.minX, y: frame.minY },
      style: {
        width: `${Math.max(240, frame.maxX - frame.minX)}px`,
        height: `${Math.max(140, frame.maxY - frame.minY)}px`,
        backgroundColor: `${frame.color}18`,
        border: `1px solid ${frame.color}55`,
        borderRadius: '24px',
        zIndex: -10,
      },
      data: { label: frame.label },
      draggable: false,
      selectable: false,
    })
  }

  for (const item of ordered) {
    visibleNodes.push({
      id: item.id,
      type: 'person',
      position: { x: item.x, y: item.y },
      data: {
        id: item.node?.id,
        name: item.node?.name || item.id,
        gender: item.node?.gender,
        generation: item.generation,
        born: item.node?.birthDate,
        died: item.node?.deathDate,
        spouse: item.spouseNames || undefined,
        branchLabel: item.branchInfo.label === '主源' ? '' : item.branchInfo.label,
        branchColor: item.branchInfo.color,
        isMainLine: item.isMainLine,
        hasChildren: item.hasChildren,
        childCount: item.childCount,
        descendantCount: item.descendantCount,
        isCollapsed: item.isCollapsed,
        visibilityScope: item.node?.visibilityScope || 'full',
        visibilityLabel: item.node?.visibilityLabel || '',
      },
      draggable: true,
      zIndex: item.isMainLine ? 20 : 10,
    })
  }

  return { nodes: visibleNodes, edges: visibleEdges }
}

function rebuildFlow() {
  const { nodes, edges } = flattenTreeWithDagre(tree.value)
  flowNodes.value = nodes
  flowEdges.value = edges
}

function toggleTreeBranch(id) {
  const key = String(id)
  const next = new Set(collapsedBranchIds.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsedBranchIds.value = next
  rebuildFlow()
}

function expandAllTreeBranches() {
  collapsedBranchIds.value = new Set()
  rebuildFlow()
}

function collapseTreeToMainLine() {
  const next = new Set()
  function walk(node) {
    if (!node) return
    const id = nodeKey(node)
    if (!mainLineIds.value.has(id) && (node.children || []).length) next.add(id)
    ;(node.children || []).forEach(walk)
  }
  ;(tree.value || []).forEach(walk)
  collapsedBranchIds.value = next
  rebuildFlow()
}

function expandTreeToGeneration(generation) {
  const next = new Set()
  function walk(node, depth = 1) {
    if (!node) return
    const gen = Number(node.generation || node.generationNo || depth)
    if (gen >= generation && (node.children || []).length) next.add(nodeKey(node))
    ;(node.children || []).forEach(child => walk(child, gen + 1))
  }
  ;(tree.value || []).forEach(root => walk(root, Number(root.generation || root.generationNo || 1)))
  collapsedBranchIds.value = next
  rebuildFlow()
}

function onFlowNodeClick(evt) {
  const id = Number(evt.node?.data?.id)
  const m = members.value.find(x => Number(x.id) === id)
  if (m) {
    activeTreeMemberId.value = m.id
    openMember(m)
  }
}

function openMember(memberOrId) {
  if (memberOrId === null || memberOrId === undefined) return
  const targetId = typeof memberOrId === 'object'
    ? Number(memberOrId.id)
    : Number(memberOrId)
  const fresh = members.value.find(x => Number(x.id) === targetId) || (typeof memberOrId === 'object' ? memberOrId : null)
  if (!fresh) return
  selected.value = fresh
  selectedCitations.value = []
  activeTreeMemberId.value = fresh.id ?? null
  drawer.value = true
  loadMemberCitations(fresh.id)
}

function locateMemberInTree(memberOrId) {
  if (memberOrId === null || memberOrId === undefined) return
  const targetId = typeof memberOrId === 'object'
    ? Number(memberOrId.id)
    : Number(memberOrId)
  const fresh = members.value.find(x => Number(x.id) === targetId) || (typeof memberOrId === 'object' ? memberOrId : null)
  if (!fresh) return
  selected.value = fresh
  activeTreeMemberId.value = fresh.id ?? null
  tab.value = 'tree'
  drawer.value = false
}

function openCreateForm() {
  if (!can('member.create')) return
  editingMember.value = null
  formVisible.value = true
}

function startEdit(m) {
  if (!can('member.edit_profile')) return
  editingMember.value = m
  formVisible.value = true
}

function onDrawerEdit(m) {
  drawer.value = false
  startEdit(m)
}

async function onDrawerDelete(m) {
  drawer.value = false
  await confirmDelete(m)
}

async function onFormSubmit(formData) {
  savingForm.value = true
  try {
    // map camelCase form fields to snake_case backend fields
    const payload = {
      name: formData.name,
      former_name: formData.formerName || null,
      courtesy_name: formData.courtesyName || null,
      art_name: formData.artName || null,
      childhood_name: formData.childhoodName || null,
      gender: formData.gender || null,
      generation: formData.generation ?? null,
      generation_name: formData.generationName || null,
      rank_no: formData.rankNo ?? null,
      rank_title: formData.rankTitle || null,
      branch: formData.branch || null,
      is_core_member: formData.isCoreMember !== false,
      spouse_ids: Array.isArray(formData.spouseIds) ? formData.spouseIds : [],
      father_id: formData.fatherId ?? null,
      mother_id: formData.motherId ?? null,
      spouse_name: null,
      father_name: null,
      mother_name: null,
      children_note: formData.childrenNote || null,
      marriage_year: formData.marriageYear || null,
      marriage_note: formData.marriageNote || null,
      birth_place: formData.birthPlace || null,
      death_place: formData.deathPlace || null,
      residence: formData.residence || null,
      ancestral_origin: formData.ancestralOrigin || null,
      burial_place: formData.burialPlace || null,
      burial_lat: formData.burialLat === null || formData.burialLat === undefined || formData.burialLat === '' ? null : Number(formData.burialLat),
      burial_lng: formData.burialLng === null || formData.burialLng === undefined || formData.burialLng === '' ? null : Number(formData.burialLng),
      photo_path: formData.photoUrl || null,
      birth_date: formData.birthDate || null,
      birth_calendar: formData.birthCalendar || null,
      birth_lunar_date: formData.birthLunarDate || null,
      birth_is_leap_month: formData.birthIsLeapMonth === true,
      birth_date_text: formData.birthDateText || null,
      death_date: formData.isLiving ? null : (formData.deathDate || null),
      death_calendar: formData.isLiving ? null : (formData.deathCalendar || null),
      death_lunar_date: formData.isLiving ? null : (formData.deathLunarDate || null),
      death_is_leap_month: formData.isLiving ? false : (formData.deathIsLeapMonth === true),
      death_date_text: formData.isLiving ? null : (formData.deathDateText || null),
      is_living: formData.isLiving !== false,
      education: formData.education || null,
      occupation: formData.occupation || null,
      position_title: formData.positionTitle || null,
      biography: formData.biography || null,
      source: formData.source || null,
      is_public: formData.isPublic !== false,
      privacy_level: formData.privacyLevel || 'public',
    }
    let savedMember = null
    if (editingMember.value?.id) {
      const { data } = await api.put(`/members/${editingMember.value.id}`, payload)
      savedMember = data?.member || data
      if (data?.pendingReview) ElMessage.warning('结构字段变更已提交审核，普通资料已保存')
      else ElMessage.success(`${savedMember.name} 已更新`)
    } else {
      const { data } = await api.post('/members', payload)
      savedMember = data
      ElMessage.success(`${data.name} 已添加`)
    }
    if (formData.photoFile && savedMember?.id) {
      const photoFormData = new FormData()
      photoFormData.append('file', formData.photoFile)
      await api.post(`/members/${savedMember.id}/photo`, photoFormData, { headers: { 'Content-Type': 'multipart/form-data' } })
      ElMessage.success('照片已同步')
    }
    formVisible.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    savingForm.value = false
  }
}

async function confirmDelete(m) {
  if (!can('member.delete')) return
  try {
    await ElMessageBox.confirm(
      `确定删除「${m.name}」？此操作不可撤销。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete(`/members/${m.id}`)
    ElMessage.success(`已删除 ${m.name}`)
    await loadAll()
  } catch {
    // cancelled
  }
}

async function uploadMemberPhoto({ member, file }) {
  if (!can('member.edit_profile') || !member?.id) return
  const raw = file?.raw
  if (!raw) return
  const formData = new FormData()
  formData.append('file', raw)
  try {
    const { data } = await api.post(`/members/${member.id}/photo`, formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    selected.value = data
    await loadAll()
    selected.value = members.value.find(x => Number(x.id) === Number(member.id)) || data
    ElMessage.success('照片已更新')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传照片失败')
  }
}

function applyTheme() {
  document.documentElement.setAttribute('data-theme', darkMode.value ? 'dark' : 'light')
  localStorage.setItem('theme', darkMode.value ? 'dark' : 'light')
}

function toggleTheme() {
  darkMode.value = !darkMode.value
  applyTheme()
}

async function loadAll() {
  loading.value = true
  try {
    const [{ data: me }, { data: s }] = await Promise.all([
      api.get('/me'),
      api.get('/settings'),
    ])
    currentUser.value = me || currentUser.value
    
    // Load families if user has permission
    if (can('family.view')) {
      try {
        const { data: fams } = await api.get('/families')
        families.value = fams || []
        
        // Set current family from localStorage or use primary family
        const savedFamilyId = localStorage.getItem('currentFamilyId')
        if (savedFamilyId && families.value.find(f => f.id === parseInt(savedFamilyId))) {
          currentFamilyId.value = parseInt(savedFamilyId)
        } else {
          const primaryFamily = families.value.find(f => f.isPrimary)
          currentFamilyId.value = primaryFamily ? primaryFamily.id : (families.value[0]?.id || null)
        }
        
        if (currentFamilyId.value) {
          currentFamily.value = families.value.find(f => f.id === currentFamilyId.value)
        }
      } catch (e) {
        console.warn('Failed to load families:', e)
      }
    }
    
    const requests = [api.get('/members')]
    
    // Load tree filtered by current family if available
    if (currentFamilyId.value) {
      requests.push(api.get(`/families/${currentFamilyId.value}/tree`))
    } else {
      requests.push(api.get('/tree'))
    }
    
    if (can('backup.view')) requests.push(api.get('/admin/backups'))
    const results = await Promise.all(requests)
    const [m, t, b] = results
    members.value = m?.data || []
    
    // Handle tree response format (may be {nodes: [...]} or [...])
    const treeData = t?.data
    tree.value = Array.isArray(treeData) ? treeData : (treeData?.nodes || [])
    
    backups.value = can('backup.view') ? (b?.data || []) : []
    settings.value = { ...settings.value, ...(s || {}) }
    if (can('user.view')) await loadUsers()
    if (can('audit.view')) await loadAuditLogs()
    if (can('quality.view')) await loadQualityReport()
    if (can('review.view')) await loadReviewRequests()
    if (can('source.view')) await loadSources()
    if (!canOpenSettingsPanel.value && tab.value === 'settings') tab.value = 'tree'
    if (!can('backup.view') && tab.value === 'backup') tab.value = 'tree'
    rebuildFlow()
  } catch (e) {
    if (e?.response?.status === 401) {
      logout()
      return
    }
    throw e
  } finally {
    loading.value = false
  }
}

async function switchFamily(familyId) {
  if (!familyId) return
  currentFamilyId.value = familyId
  currentFamily.value = families.value.find(f => f.id === familyId)
  localStorage.setItem('currentFamilyId', familyId)
  
  // Reload tree for the selected family
  try {
    const { data } = await api.get(`/families/${familyId}/tree`)
    tree.value = Array.isArray(data) ? data : (data?.nodes || [])
    rebuildFlow()
    ElMessage.success(`已切换到 ${currentFamily.value?.name || '选中家族'}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '切换家族失败')
  }
}

async function loadUsers() {
  if (!can('user.view')) return
  userLoading.value = true
  try {
    const [{ data: u }, { data: r }] = await Promise.all([
      api.get('/admin/users'),
      api.get('/admin/roles'),
    ])
    users.value = u || []
    roles.value = r || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载用户列表失败')
  } finally {
    userLoading.value = false
  }
}

async function loadAuditLogs() {
  if (!can('audit.view')) return
  try {
    const { data } = await api.get('/admin/audit-logs')
    auditLogs.value = data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载审计日志失败')
  }
}

async function loadQualityReport() {
  if (!can('quality.view')) return
  try {
    const { data } = await api.get('/admin/data-quality')
    qualityReport.value = data || { summary: { total: 0, bySeverity: {}, byCategory: {} }, issues: [] }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载数据质量报告失败')
  }
}

async function loadReviewRequests() {
  if (!can('review.view')) return
  try {
    const { data } = await api.get('/admin/review-requests')
    reviewRequests.value = data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载审核请求失败')
  }
}

async function loadSources() {
  if (!can('source.view')) return
  try {
    const { data } = await api.get('/sources')
    sources.value = data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载来源库失败')
  }
}

async function loadMemberCitations(memberOrId) {
  const memberId = typeof memberOrId === 'object' ? memberOrId?.id : memberOrId
  if (!can('source.view') || !memberId) {
    selectedCitations.value = []
    return
  }
  citationLoading.value = true
  try {
    const { data } = await api.get(`/members/${memberId}/citations`)
    selectedCitations.value = data || []
  } catch (e) {
    selectedCitations.value = []
    ElMessage.error(e.response?.data?.detail || '加载引用记录失败')
  } finally {
    citationLoading.value = false
  }
}

async function createMemberCitation({ memberId, payload, done }) {
  if (!can('source.manage') || !memberId) return
  try {
    await api.post(`/members/${memberId}/citations`, payload)
    ElMessage.success('引用记录已添加')
    done?.()
    await Promise.all([loadMemberCitations(memberId), loadQualityReport(), loadAuditLogs()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加引用失败')
  }
}

async function approveReview(row) {
  if (!can('review.approve') || !row?.id) return
  try {
    await api.post(`/admin/review-requests/${row.id}/approve`)
    ElMessage.success('审核已通过')
    await Promise.all([loadReviewRequests(), loadAll(), loadAuditLogs()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '审核通过失败')
  }
}

async function rejectReview({ row, note }) {
  if (!can('review.approve') || !row?.id) return
  try {
    await api.post(`/admin/review-requests/${row.id}/reject`, { note })
    ElMessage.success('审核已驳回')
    await Promise.all([loadReviewRequests(), loadAuditLogs()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '驳回失败')
  }
}

async function createSource({ payload, done }) {
  if (!can('source.manage')) return
  try {
    await api.post('/sources', payload)
    ElMessage.success('来源已创建')
    done?.()
    await Promise.all([loadSources(), loadQualityReport(), loadAuditLogs()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建来源失败')
  }
}

async function updateSource({ id, payload, done }) {
  if (!can('source.manage')) return
  try {
    await api.put(`/sources/${id}`, payload)
    ElMessage.success('来源已更新')
    done?.()
    await Promise.all([loadSources(), loadAuditLogs()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新来源失败')
  }
}

async function deleteSource(row) {
  if (!can('source.manage') || !row?.id) return
  try {
    await ElMessageBox.confirm(`确定删除来源「${row.title}」？`, '确认删除来源', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await api.delete(`/sources/${row.id}`)
    ElMessage.success('来源已删除')
    await Promise.all([loadSources(), loadQualityReport(), loadAuditLogs()])
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e.response?.data?.detail || '删除来源失败')
  }
}

async function exportGedcom() {
  if (!can('export.gedcom')) return
  try {
    const { data } = await api.get('/export/gedcom', { responseType: 'blob' })
    const blobUrl = window.URL.createObjectURL(new Blob([data], { type: 'text/plain;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = `family-tree-${Date.now()}.ged`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导出 GEDCOM 失败')
  }
}

async function createUser({ payload, done }) {
  if (!can('user.create')) return
  try {
    await api.post('/admin/users', payload)
    ElMessage.success('用户已创建')
    done?.()
    await Promise.all([loadUsers(), loadAuditLogs()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建用户失败')
  }
}

async function updateUser({ id, payload, done }) {
  if (!can('user.edit_role')) return
  try {
    await api.put(`/admin/users/${id}`, payload)
    ElMessage.success('用户已更新')
    done?.()
    await Promise.all([loadUsers(), loadAuditLogs()])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新用户失败')
  }
}

async function toggleUserActive(row) {
  if (!can('user.disable')) return
  try {
    await ElMessageBox.confirm(`确定${row.isActive ? '停用' : '启用'}账号「${row.username}」？`, '确认操作', {
      confirmButtonText: row.isActive ? '停用' : '启用',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await api.post(`/admin/users/${row.id}/${row.isActive ? 'disable' : 'enable'}`)
    ElMessage.success('账号状态已更新')
    await Promise.all([loadUsers(), loadAuditLogs()])
  } catch {
    // cancelled
  }
}

async function resetUserPassword({ id, password, done }) {
  if (!can('user.reset_password')) return
  try {
    await api.post(`/admin/users/${id}/reset-password`, { password })
    ElMessage.success('密码已重置')
    done?.()
    await loadAuditLogs()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重置密码失败')
  }
}

async function saveSettings(payload) {
  if (!can('settings.edit_basic')) return
  savingSettings.value = true
  try {
    const { data } = await api.put('/settings', payload)
    settings.value = { ...settings.value, ...(data || {}) }
    ElMessage.success('设置已保存')
    await loadAuditLogs()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存设置失败')
  } finally {
    savingSettings.value = false
  }
}

async function updateMemberVisibleFields(fields) {
  if (!can('settings.edit_display')) return
  const nextSettings = { ...settings.value, memberVisibleFields: fields }
  savingSettings.value = true
  try {
    const { data } = await api.put('/settings', nextSettings)
    settings.value = { ...settings.value, ...(data || {}), memberVisibleFields: data?.memberVisibleFields || fields }
    ElMessage.success('成员录显示字段已更新')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存显示字段失败')
  } finally {
    savingSettings.value = false
  }
}

// Family management functions
async function saveFamily({ family, form, done }) {
  try {
    if (family?.id) {
      // Update existing family
      await api.put(`/families/${family.id}`, form)
      ElMessage.success('家族信息已更新')
    } else {
      // Create new family (not implemented in backend yet, but structure is ready)
      ElMessage.warning('创建新家族功能待实现')
      return
    }
    
    // Reload families
    const { data: fams } = await api.get('/families')
    families.value = fams || []
    
    if (done) done()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存家族失败')
  }
}

async function loadFamilyUsers({ familyId, callback }) {
  try {
    const { data } = await api.get(`/families/${familyId}/users`)
    if (callback) callback(data || [])
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载家族用户失败')
  }
}

async function addFamilyUser({ familyId, userId, role, done }) {
  try {
    await api.post(`/families/${familyId}/users`, { userId, role })
    ElMessage.success('用户已添加到家族')
    if (done) done()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加用户失败')
  }
}

async function removeFamilyUser({ familyId, userId, done }) {
  try {
    await api.delete(`/families/${familyId}/users/${userId}`)
    ElMessage.success('用户已从家族移除')
    if (done) done()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '移除用户失败')
  }
}

async function importDefault() {
  if (!can('member.import')) return
  ElMessage.warning('已取消直接导入内置数据，请下载样表填写后上传')
}

async function downloadImportTemplate() {
  if (!can('member.import')) return
  try {
    const { data } = await api.get('/import/template', { responseType: 'blob' })
    const blobUrl = window.URL.createObjectURL(new Blob([data]))
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = '家谱成员导入样表.xlsx'
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(blobUrl)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '下载样表失败')
  }
}

async function uploadMemberExcel(uploadFile) {
  if (!can('member.import')) return
  const raw = uploadFile?.raw
  if (!raw) return
  try {
    await ElMessageBox.confirm(
      '上传成员表格会先自动备份当前数据库，然后用表格内容替换现有成员数据。确定继续？',
      '确认导入成员表格',
      { confirmButtonText: '上传导入', cancelButtonText: '取消', type: 'warning' }
    )
    const formData = new FormData()
    formData.append('file', raw)
    const { data } = await api.post('/import/excel', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    await loadAll()
    await loadAuditLogs()
    ElMessage.success(`导入成功，共 ${data?.count || 0} 条成员`)
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e.response?.data?.detail || '导入失败，请检查表格格式')
  }
}

async function backup() {
  if (!can('backup.create')) return
  await api.post('/admin/backup')
  await loadAll()
  await loadAuditLogs()
  ElMessage.success('备份成功')
}

async function downloadBackup(row) {
  if (!can('backup.download')) return
  if (!row?.file) {
    ElMessage.error('下载失败')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定下载备份「${row.file}」？备份文件包含完整家谱隐私数据，请妥善保存。`,
      '确认下载备份',
      { confirmButtonText: '下载', cancelButtonText: '取消', type: 'warning' }
    )
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    throw e
  }
  api.get(`/admin/backups/${encodeURIComponent(row.file)}/download`, { responseType: 'blob' })
    .then(({ data }) => {
      const blobUrl = window.URL.createObjectURL(new Blob([data]))
      const link = document.createElement('a')
      link.href = blobUrl
      link.download = row.file
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(blobUrl)
    })
    .catch(() => {
      ElMessage.error('下载失败')
    })
}

async function restoreBackup(row) {
  if (!can('backup.restore') || !row?.file) return
  try {
    await ElMessageBox.confirm(
      `确定将数据库恢复到备份「${row.file}」？系统会先自动创建恢复前保护备份。`,
      '确认恢复备份',
      { confirmButtonText: '恢复', cancelButtonText: '取消', type: 'warning' }
    )
    const { data } = await api.post(`/admin/restore/${encodeURIComponent(row.file)}`)
    ElMessage.success(`已恢复备份 ${row.file}，保护备份：${data?.safetyBackup?.file || '已创建'}`)
    await loadAll()
    await loadAuditLogs()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    if (e?.response?.status === 401) {
      logout()
      return
    }
    ElMessage.error(e.response?.data?.detail || '恢复备份失败')
  }
}

async function deleteBackup(row) {
  if (!can('backup.delete')) return
  try {
    await ElMessageBox.confirm(
      `确定删除备份「${row.file}」？此操作不可撤销。`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await api.delete(`/admin/backups/${encodeURIComponent(row.file)}`)
    ElMessage.success(`已删除备份 ${row.file}`)
    await loadAll()
    await loadAuditLogs()
  } catch {
    // cancelled
  }
}

async function uploadBackup(file) {
  if (!can('backup.restore')) return
  if (!file?.raw) {
    ElMessage.error('上传失败：文件无效')
    return
  }
  
  // 检查文件格式
  if (!file.name.endsWith('.db')) {
    ElMessage.error('仅支持 .db 格式的 SQLite 备份文件')
    return
  }
  
  // 检查文件大小（限制 100MB）
  const maxSize = 100 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.error('文件过大，最大支持 100MB')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定上传备份文件「${file.name}」？上传后可在列表中找到并恢复。`,
      '确认上传备份',
      { confirmButtonText: '上传', cancelButtonText: '取消', type: 'info' }
    )
    
    const formData = new FormData()
    formData.append('file', file.raw)
    
    loading.value = true
    const { data } = await api.post('/admin/backups/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    ElMessage.success(`备份文件已上传：${data.filename}`)
    await loadAll()
    await loadAuditLogs()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    if (e?.response?.status === 401) {
      logout()
      return
    }
    ElMessage.error(e.response?.data?.detail || '上传备份失败')
  } finally {
    loading.value = false
  }
}

function logout() {
  localStorage.removeItem('token')
  currentUser.value = { id: 0, username: '', displayName: '访客', role: 'viewer', capabilities: [], isActive: true, memberId: null }
  router.push('/login')
}

onMounted(() => {
  applyTheme()
  loadAll()
})
</script>
