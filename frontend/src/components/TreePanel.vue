<template>
  <div class="tree-panel lineage-workbench" data-testid="tree-panel-boundary">
    <div class="tree-toolbar tree-toolbar--lineage lineage-toolbar-v2">
      <div class="tree-toolbar__summary">
        <span class="tree-toolbar__eyebrow">壹 · 家族世系</span>
        <div class="tree-toolbar__title">族谱阅读与关系全景</div>
        <div class="tree-toolbar__desc">
          成员 {{ memberCount }} · 世代 {{ generationColumns.length || generationCount }} · 分支 {{ branchOptions.length - 1 }} · 当前 {{ modeLabel }}
        </div>
      </div>

      <div class="lineage-toolbar-v2__controls">
        <el-radio-group v-model="displayMode" size="small">
          <el-radio-button label="reader">族谱阅读</el-radio-button>
          <el-radio-button label="flow">全景关系图</el-radio-button>
        </el-radio-group>
        <el-input
          v-model="searchKeyword"
          class="lineage-search"
          size="small"
          clearable
          placeholder="搜索姓名 / 支系 / 配偶"
        />
        <el-select v-model="generationLimit" size="small" class="generation-limit-select">
          <el-option label="显示三世" value="3" />
          <el-option label="显示五世" value="5" />
          <el-option label="显示全部" value="all" />
        </el-select>
      </div>

      <div class="tree-toolbar__actions">
        <template v-if="displayMode === 'flow'">
          <el-button size="small" :disabled="centerHistoryStack.length === 0" @click="goBackCenter">返回上级</el-button>
          <el-button size="small" @click="resetToAncestor">返回始祖</el-button>
          <el-button size="small" type="primary" plain @click="resetSunburstView">重置视图</el-button>
        </template>
        <template v-else>
          <el-button size="small" @click="resetReaderFilters">重置筛选</el-button>
          <el-button size="small" type="primary" plain @click="switchToFlowAndReset">查看全景</el-button>
        </template>
      </div>
    </div>

    <div v-if="displayMode !== 'flow'" class="lineage-reader-shell">
      <aside class="lineage-branch-sidebar">
        <div class="sidebar-title">分支 / 房支</div>
        <button
          v-for="branch in branchOptions"
          :key="branch.key"
          class="branch-filter-item"
          :class="branchFilter === branch.key ? 'active' : ''"
          type="button"
          @click="setBranchFilter(branch.key)"
        >
          <span class="branch-filter-dot" :style="{ backgroundColor: branch.color }"></span>
          <span class="branch-filter-label">{{ branch.label }}</span>
          <small>{{ branch.count }}</small>
        </button>
      </aside>

      <main class="lineage-reader-main">
        <div class="reader-status-bar">
          <div>
            <b>族谱阅读模式</b>
            <span>按世代横向分列，配偶与支系在人物卡内呈现，更适合日常浏览。</span>
          </div>
          <el-tag type="info" effect="plain">当前显示 {{ visibleReaderItems.length }} 人</el-tag>
        </div>

        <div v-if="generationColumns.length" class="lineage-generation-board">
          <section v-for="column in generationColumns" :key="column.generation" class="generation-column">
            <header class="generation-column__header">
              <strong>第{{ column.generation }}代</strong>
              <small>{{ column.items.length }} 人</small>
            </header>
            <div class="generation-card-stack">
              <article
                v-for="item in column.items"
                :key="item.id"
                class="reader-person-card"
                :class="[
                  item.gender === '女' ? 'female' : 'male',
                  item.isMainLine ? 'is-main-line' : '',
                  item.matchesSearch ? 'matches-search' : '',
                  Number(item.id) === Number(currentFocusMemberId) ? 'active' : ''
                ]"
                :style="{ '--branch-color': item.branchColor }"
                tabindex="0"
                @click="selectMember(item.id)"
                @keyup.enter="selectMember(item.id)"
              >
                <div class="reader-person-card__top">
                  <span class="node-gender-dot" :class="item.gender === '女' ? 'female' : 'male'"></span>
                  <span>{{ item.gender || '未知' }}</span>
                  <span v-if="item.branchLabel" class="reader-branch-pill">{{ item.branchLabel }}</span>
                  <span v-if="item.isMainLine" class="reader-main-pill">主线</span>
                  <span v-if="item.visibilityScope === 'basic'" class="reader-relation-pill">关系可见</span>
                </div>
                <h3>{{ item.name }}</h3>
                <div class="reader-person-card__meta">
                  <span v-if="item.generationName">{{ item.generationName }}字辈</span>
                  <span v-if="item.rankTitle">{{ item.rankTitle }}</span>
                  <span>{{ item.birthDate || '生年不详' }}<template v-if="item.deathDate"> - {{ item.deathDate }}</template></span>
                </div>
                <div v-if="item.spouseNames" class="reader-person-card__relation">配偶：{{ item.spouseNames }}</div>
                <div class="reader-person-card__footer">
                  <span>子女 {{ item.childCount }}</span>
                  <span v-if="item.privacyLabel">{{ item.privacyLabel }}</span>
                  <span :class="item.hasSource ? 'has-source' : 'missing-source'">{{ item.hasSource ? '有来源' : '待补来源' }}</span>
                </div>
              </article>
            </div>
          </section>
        </div>
        <el-empty v-else description="没有匹配的世系成员" />
      </main>

      <aside class="lineage-focus-sidebar">
        <div class="sidebar-title">当前成员摘要</div>
        <div v-if="summaryMember" class="summary-member-card">
          <div class="summary-avatar" :class="summaryMember.gender === '女' ? 'female' : 'male'">{{ summaryMember.name?.slice(0, 1) || '人' }}</div>
          <h3>{{ summaryMember.name }}</h3>
          <p>第{{ summaryMember.generation ?? '?' }}代 · {{ summaryMember.gender || '未知' }}</p>
          <div class="summary-facts">
            <div><span>出生</span><b>{{ summaryMember.birthDate || summaryMember.birthDateText || '未记录' }}</b></div>
            <div><span>支系</span><b>{{ summaryMember.branch || '未分支' }}</b></div>
            <div><span>配偶</span><b>{{ summarySpouseText || '未记录' }}</b></div>
            <div><span>子女</span><b>{{ focusChildren.length }} 人</b></div>
          </div>
          <div class="summary-actions">
            <el-button type="primary" size="small" @click="selectMember(summaryMember.id)">查看档案</el-button>
          </div>
        </div>
        <el-empty v-else description="点击成员卡查看摘要" />
      </aside>
    </div>

    <div v-else class="tree-wrap flow-wrap sunburst-wrap">
      <div ref="chartRef" class="sunburst-chart-canvas"></div>

      <!-- Floating Legend -->
      <div class="flow-chart-legend">
        <div class="legend-title">图谱图例</div>
        <div class="legend-group">
          <div class="legend-group-title">关系连线</div>
          <div class="legend-item">
            <span class="legend-line line-spouse"></span>
            <span>配偶 (亮红实体弧线)</span>
          </div>
          <div class="legend-item">
            <span class="legend-line line-child"></span>
            <span>子女 (蓝色指向箭头)</span>
          </div>
          <div class="legend-item">
            <span class="legend-pin"></span>
            <span>远距跨圈导航图钉</span>
          </div>
        </div>
        <div class="legend-group">
          <div class="legend-group-title">人物年代/状态</div>
          <div class="legend-item">
            <span class="legend-dot dot-millennial"></span>
            <span>2000年后出生 (粉红)</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot dot-modern"></span>
            <span>1970-1999出生 (橙黄)</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot dot-classic"></span>
            <span>1970前/生年不详 (蔚蓝)</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot dot-deceased"></span>
            <span>已故成员 (灰色+斜纹)</span>
          </div>
          <div class="legend-item">
            <span class="legend-dot dot-active"></span>
            <span>当前选中/查看中</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
/**
 * TreePanel visualizes lineage in two modes:
 * - reader: scrollable generation columns for daily genealogy reading
 * - flow: ECharts Sunburst panorama for complex relation inspection
 */
import { computed, nextTick, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { FAMILY_HUE_PRESETS, getFamilySurname, getBaseHueForSurname, generateFamilyPalette } from '../utils/genealogy'
import { fetchAuthenticatedObjectUrl, revokeObjectUrl } from '../utils/authenticatedAsset'

const props = defineProps({
  tree: { type: Array, default: () => [] },
  members: { type: Array, default: () => [] },
  activeMemberId: { type: [Number, String], default: null },
  familyName: { type: String, default: '王氏家族' },
})

const emit = defineEmits(['node-click'])

const displayMode = ref('reader')
const searchKeyword = ref('')
const branchFilter = ref('all')
const localFocusMemberId = ref(null)
const generationLimit = ref('5')
const currentCenterMemberId = ref(null)
const centerHistoryStack = ref([])

const chartRef = ref(null)
let chartInstance = null

const authenticatedPhotos = ref(new Map())

async function loadMemberPhotos() {
  for (const m of props.members || []) {
    const mid = Number(m.id)
    if (m.photoUrl && !authenticatedPhotos.value.has(mid)) {
      try {
        const blobUrl = await fetchAuthenticatedObjectUrl(m.photoUrl)
        authenticatedPhotos.value.set(mid, blobUrl)
        if (displayMode.value === 'flow') {
          renderChart()
        }
      } catch (err) {
        console.error(`Failed to load photo for member ${mid}:`, err)
      }
    }
  }
}

function clearMemberPhotos() {
  for (const url of authenticatedPhotos.value.values()) {
    revokeObjectUrl(url)
  }
  authenticatedPhotos.value.clear()
}

watch(() => props.members, () => {
  loadMemberPhotos()
}, { immediate: true, deep: true })

const branchPalette = computed(() => {
  const surname = getFamilySurname(props.familyName)
  const hue = getBaseHueForSurname(surname)
  return generateFamilyPalette(hue)
})

// ECharts Sunburst Chart Implementation
function initChart() {
  if (!chartRef.value) return
  if (chartInstance) {
    chartInstance.dispose()
  }
  chartInstance = echarts.init(chartRef.value)
  renderChart()
  
  chartInstance.on('click', (params) => {
    if (params.data && params.data.id) {
      let id = String(params.data.id)
      if (id.startsWith('shortcut-')) {
        const parts = id.split('-')
        id = parts[parts.length - 1]
      }
      if (!id.includes('midpoint')) {
        setLocalFocus(id)
        emit('node-click', id)
      }
    }
  })

  chartInstance.on('dblclick', (params) => {
    if (params.data && params.data.id) {
      let id = String(params.data.id)
      if (id.startsWith('shortcut-')) {
        const parts = id.split('-')
        id = parts[parts.length - 1]
      }
      if (!id.includes('midpoint')) {
        setCenterMember(id)
      }
    }
  })
}

function filterSunburstNode(node, isSearchActive, keyword) {
  const data = node.rawMember || {}
  const spouseNames = (data.spouses || []).map(s => s.name).filter(Boolean).join('、') || data.spouse || ''
  const searchHaystack = [
    data.name,
    data.branch,
    data.generationName,
    data.rankTitle,
    spouseNames,
    data.birthPlace,
    data.residence
  ].filter(Boolean).join(' ').toLowerCase()
  
  const matches = isSearchActive && searchHaystack.includes(keyword)
  
  let childrenMatches = false
  const children = []
  if (node.children) {
    for (const child of node.children) {
      const childResult = filterSunburstNode(child, isSearchActive, keyword)
      if (childResult.hasMatch) {
        childrenMatches = true
      }
      children.push(childResult.node)
    }
  }
  
  const hasMatch = matches || childrenMatches
  
  const itemStyle = { ...node.itemStyle }
  const labelStyle = { ...node.label }
  
  if (isSearchActive) {
    if (matches) {
      itemStyle.opacity = 1.0
      itemStyle.borderColor = '#d3a26a'
      itemStyle.borderWidth = 3
      labelStyle.fontWeight = 'bold'
    } else if (childrenMatches) {
      itemStyle.opacity = 0.65
      itemStyle.borderWidth = 1
    } else {
      itemStyle.opacity = 0.12
      itemStyle.borderWidth = 0.5
    }
  } else {
    itemStyle.opacity = 1.0
    itemStyle.borderColor = '#ffffff'
    itemStyle.borderWidth = 1
  }
  
  return {
    hasMatch,
    node: {
      ...node,
      children: children.length ? children : undefined,
      itemStyle,
      label: {
        ...node.label,
        ...labelStyle
      }
    }
  }
}

function getBirthYear(m) {
  const dateStr = m.birthDate || m.birthLunarDate || m.birthDateText || ''
  const match = dateStr.match(/(\d{4})/)
  if (match) return Number(match[1])
  return null
}

function buildRelationGraph(members) {
  const graph = new Map() // memberId -> Set of neighborIds
  const memberById = new Map()
  for (const m of members) {
    const mid = Number(m.id)
    memberById.set(mid, m)
    if (!graph.has(mid)) {
      graph.set(mid, new Set())
    }
  }

  function addEdge(id1, id2) {
    id1 = Number(id1)
    id2 = Number(id2)
    if (id1 === id2) return
    if (graph.has(id1) && graph.has(id2)) {
      graph.get(id1).add(id2)
      graph.get(id2).add(id1)
    }
  }

  // Add spouse and parent edges
  for (const m of members) {
    const mid = Number(m.id)
    if (m.fatherId) addEdge(mid, m.fatherId)
    if (m.motherId) addEdge(mid, m.motherId)
    if (Array.isArray(m.spouseIds)) {
      for (const sid of m.spouseIds) {
        addEdge(mid, sid)
      }
    }
  }

  // Add sibling edges (sharing same father or mother)
  for (let i = 0; i < members.length; i++) {
    for (let j = i + 1; j < members.length; j++) {
      const m1 = members[i]
      const m2 = members[j]
      const isSibling = (m1.fatherId && m1.fatherId === m2.fatherId) || 
                        (m1.motherId && m1.motherId === m2.motherId)
      if (isSibling) {
        addEdge(Number(m1.id), Number(m2.id))
      }
    }
  }

  return { graph, memberById }
}

function findDefaultCenterMember() {
  if (!props.members || props.members.length === 0) return null
  let lowestGen = Infinity
  let candidates = []
  for (const m of props.members) {
    const g = m.generation ?? m.generationNo
    if (g !== null && g !== undefined) {
      const genNum = Number(g)
      if (genNum < lowestGen) {
        lowestGen = genNum
        candidates = [m]
      } else if (genNum === lowestGen) {
        candidates.push(m)
      }
    }
  }
  if (candidates.length === 0) return props.members[0].id
  const rootCand = candidates.find(c => !c.fatherId && !c.motherId) || candidates[0]
  return rootCand.id
}

function computeLayout(members, centerId) {
  const { graph, memberById } = buildRelationGraph(members)
  
  if (!graph.has(centerId)) {
    return { nodes: [], links: [], maxDistance: 1 }
  }

  // BFS to assign distances and build spanning tree
  const distance = new Map() // memberId -> distance (0, 1, 2...)
  const bfsParent = new Map() // memberId -> parentId in tree
  const bfsChildren = new Map() // memberId -> list of childIds in tree
  
  for (const mid of graph.keys()) {
    bfsChildren.set(mid, [])
  }

  const queue = [centerId]
  distance.set(centerId, 0)
  const visited = new Set([centerId])

  while (queue.length > 0) {
    const curr = queue.shift()
    const dist = distance.get(curr)
    
    const neighbors = Array.from(graph.get(curr) || [])
    
    if (dist === 0) {
      const currMember = memberById.get(curr)
      neighbors.sort((a, b) => {
        const mA = memberById.get(a)
        const mB = memberById.get(b)
        
        function getCategoryScore(m) {
          if (!m) return 99
          const isParent = m.id === currMember.fatherId || m.id === currMember.motherId
          if (isParent) return 1 // Parents first (top)
          const isSpouse = Array.isArray(currMember.spouseIds) && currMember.spouseIds.includes(m.id)
          if (isSpouse) return 2 // Spouses second (sides)
          const isSibling = (m.fatherId && m.fatherId === currMember.fatherId) || 
                            (m.motherId && m.motherId === currMember.motherId)
          if (isSibling) return 3 // Siblings third (side-bottom)
          const isChild = m.fatherId === currMember.id || m.motherId === currMember.id
          if (isChild) return 4 // Children fourth (bottom)
          return 5
        }
        return getCategoryScore(mA) - getCategoryScore(mB)
      })
    } else {
      neighbors.sort((a, b) => {
        const mA = memberById.get(a)
        const mB = memberById.get(b)
        const genA = mA?.generation ?? 999
        const genB = mB?.generation ?? 999
        return genB - genA
      })
    }

    for (const n of neighbors) {
      if (!visited.has(n)) {
        visited.add(n)
        distance.set(n, dist + 1)
        bfsParent.set(n, curr)
        bfsChildren.get(curr).push(n)
        queue.push(n)
      }
    }
  }

  // Ring intervals
  const RingWidth = 120
  
  // Coordinates mapping in polar: memberId -> { r, thetaDegrees }
  const coords = new Map()

  // Root is at center
  coords.set(Number(centerId), { r: 0, thetaDegrees: 0 })

  // Children of root
  const rootChildren = bfsChildren.get(Number(centerId)) || []
  const rootMember = memberById.get(Number(centerId))
  
  // Helper to determine sector assignment in radians
  function getSectorRange(m) {
    if (!m) return [0, 2 * Math.PI]
    const isParent = Number(m.id) === Number(rootMember.fatherId) || Number(m.id) === Number(rootMember.motherId)
    if (isParent) return [Math.PI / 3, 2 * Math.PI / 3] // 60 to 120 deg (top)
    
    const isSpouse = Array.isArray(rootMember.spouseIds) && rootMember.spouseIds.map(Number).includes(Number(m.id))
    if (isSpouse) return [-Math.PI / 6, Math.PI / 4] // -30 to 45 deg (right)
    
    const isSibling = (m.fatherId && Number(m.fatherId) === Number(rootMember.fatherId)) || 
                      (m.motherId && Number(m.motherId) === Number(rootMember.motherId))
    if (isSibling) return [Math.PI, 5 * Math.PI / 4] // 180 to 225 deg (left-bottom)
    
    const isChild = Number(m.fatherId) === Number(rootMember.id) || Number(m.motherId) === Number(rootMember.id)
    if (isChild) return [4 * Math.PI / 3, 11 * Math.PI / 6] // 240 to 330 deg (bottom)
    
    return [Math.PI / 4, Math.PI / 3]
  }

  function assignAngles(nodeId, thetaMin, thetaMax, r) {
    const theta = (thetaMin + thetaMax) / 2
    const thetaDegrees = theta * 180 / Math.PI
    coords.set(Number(nodeId), { r, thetaDegrees })

    const children = bfsChildren.get(Number(nodeId)) || []
    if (children.length === 0) return

    const span = thetaMax - thetaMin
    const step = span / children.length
    
    const childrenMembers = children.map(cid => memberById.get(cid)).filter(Boolean)
    childrenMembers.sort((a, b) => {
      const birthA = a.birthDate || a.birthDateText || ''
      const birthB = b.birthDate || b.birthDateText || ''
      return birthA.localeCompare(birthB)
    })
    
    let currentThetaMin = thetaMin
    for (let i = 0; i < childrenMembers.length; i++) {
      const child = childrenMembers[i]
      
      let isTwin = false
      if (i < childrenMembers.length - 1) {
        const nextChild = childrenMembers[i + 1]
        const date1 = child.birthDate || child.birthDateText
        const date2 = nextChild.birthDate || nextChild.birthDateText
        if (date1 && date1 === date2 && child.fatherId && Number(child.fatherId) === Number(nextChild.fatherId) && child.motherId && Number(child.motherId) === Number(nextChild.motherId)) {
          isTwin = true
        }
      }
      
      if (isTwin) {
        const twin1Id = child.id
        const twin2Id = childrenMembers[i + 1].id
        
        const midTheta = currentThetaMin + step / 2
        assignAngles(twin1Id, currentThetaMin, midTheta, r + RingWidth)
        assignAngles(twin2Id, midTheta, currentThetaMin + step, r + RingWidth)
        
        i++
        currentThetaMin += step
      } else {
        assignAngles(child.id, currentThetaMin, currentThetaMin + step, r + RingWidth)
        currentThetaMin += step
      }
    }
  }

  function partitionSector(nodesList, thetaMin, thetaMax, r) {
    if (nodesList.length === 0) return

    const span = thetaMax - thetaMin
    const step = span / nodesList.length
    
    let currentThetaMin = thetaMin
    for (let i = 0; i < nodesList.length; i++) {
      const member = nodesList[i]
      
      let isTwin = false
      if (i < nodesList.length - 1) {
        const nextMember = nodesList[i + 1]
        const date1 = member.birthDate || member.birthDateText
        const date2 = nextMember.birthDate || nextMember.birthDateText
        if (date1 && date1 === date2 && member.fatherId && Number(member.fatherId) === Number(nextMember.fatherId) && member.motherId && Number(member.motherId) === Number(nextMember.motherId)) {
          isTwin = true
        }
      }
      
      if (isTwin) {
        const twin1 = member
        const twin2 = nodesList[i + 1]
        
        const midTheta = currentThetaMin + step / 2
        assignAngles(twin1.id, currentThetaMin, midTheta, r)
        assignAngles(twin2.id, midTheta, currentThetaMin + step, r)
        
        i++
        currentThetaMin += step
      } else {
        assignAngles(member.id, currentThetaMin, currentThetaMin + step, r)
        currentThetaMin += step
      }
    }
  }

  // Categorize direct neighbors of the root member to avoid overlap at Ring 1
  const parentsList = []
  const spousesList = []
  const siblingsList = []
  const childrenList = []
  const othersList = []

  for (const childId of rootChildren) {
    const child = memberById.get(childId)
    if (!child) continue
    const cid = Number(child.id)
    const isParent = cid === Number(rootMember.fatherId) || cid === Number(rootMember.motherId)
    const isSpouse = Array.isArray(rootMember.spouseIds) && rootMember.spouseIds.map(Number).includes(cid)
    const isSibling = (child.fatherId && Number(child.fatherId) === Number(rootMember.fatherId)) || 
                      (child.motherId && Number(child.motherId) === Number(rootMember.motherId))
    const isChild = Number(child.fatherId) === Number(rootMember.id) || Number(child.motherId) === Number(rootMember.id)

    if (isParent) parentsList.push(child)
    else if (isSpouse) spousesList.push(child)
    else if (isSibling) siblingsList.push(child)
    else if (isChild) childrenList.push(child)
    else othersList.push(child)
  }

  // Sort lists
  if (Array.isArray(rootMember.spouseIds)) {
    const spouseIdNums = rootMember.spouseIds.map(Number)
    spousesList.sort((a, b) => spouseIdNums.indexOf(Number(a.id)) - spouseIdNums.indexOf(Number(b.id)))
  }
  siblingsList.sort((a, b) => {
    const birthA = a.birthDate || a.birthDateText || ''
    const birthB = b.birthDate || b.birthDateText || ''
    return birthA.localeCompare(birthB)
  })
  childrenList.sort((a, b) => {
    const birthA = a.birthDate || a.birthDateText || ''
    const birthB = b.birthDate || b.birthDateText || ''
    return birthA.localeCompare(birthB)
  })

  // Partition sectors
  partitionSector(parentsList, Math.PI / 3, 2 * Math.PI / 3, RingWidth)
  partitionSector(spousesList, -Math.PI / 6, Math.PI / 4, RingWidth)
  partitionSector(siblingsList, Math.PI, 5 * Math.PI / 4, RingWidth)
  partitionSector(childrenList, 4 * Math.PI / 3, 11 * Math.PI / 6, RingWidth)
  partitionSector(othersList, Math.PI / 4, Math.PI / 3, RingWidth)

  // Formulate ECharts nodes and links
  const echartsNodes = []
  const echartsLinks = []
  let maxDistance = 1

  // Add all member nodes
  for (const m of members) {
    const mid = Number(m.id)
    if (!coords.has(mid)) continue
    
    const { r, thetaDegrees } = coords.get(mid)
    const dist = r / RingWidth
    if (dist > maxDistance) maxDistance = dist
    const isActive = mid === Number(currentCenterMemberId.value)
    
    const birthYear = getBirthYear(m)
    let color = '#5cb8ff'
    if (birthYear) {
      if (birthYear >= 2000) color = '#ff85a2'
      else if (birthYear >= 1970) color = '#ffbe5c'
    } else {
      color = '#e0e0e0'
    }
    
    const isDeceased = !m.isLiving || m.deathDate || m.deathDateText
    
    const thetaRad = thetaDegrees * Math.PI / 180
    const x = r * Math.cos(thetaRad)
    const y = -r * Math.sin(thetaRad)

    // Check if authenticated photo is loaded
    const photoUrl = authenticatedPhotos.value.get(mid)

    // Determine dynamic label position to avoid line collisions
    let labelPosition = 'bottom'
    if (mid === Number(centerId)) {
      labelPosition = 'left'
    } else {
      let spouseId = null
      if (Array.isArray(m.spouseIds)) {
        for (const sid of m.spouseIds) {
          if (coords.has(Number(sid))) {
            spouseId = Number(sid)
            break
          }
        }
      }

      const angle = ((thetaDegrees % 360) + 360) % 360
      const isTopOrBottom = (angle >= 45 && angle < 135) || (angle >= 225 && angle < 315)
      
      if (isTopOrBottom) {
        if (spouseId !== null && coords.has(spouseId)) {
          const cSpouse = coords.get(spouseId)
          const xNode = Math.cos(thetaDegrees * Math.PI / 180)
          const xSpouse = Math.cos(cSpouse.thetaDegrees * Math.PI / 180)
          labelPosition = xSpouse > xNode ? 'left' : 'right'
        } else {
          labelPosition = 'right'
        }
      } else {
        if (spouseId !== null && coords.has(spouseId)) {
          const cSpouse = coords.get(spouseId)
          const yNode = -Math.sin(thetaDegrees * Math.PI / 180)
          const ySpouse = -Math.sin(cSpouse.thetaDegrees * Math.PI / 180)
          labelPosition = ySpouse > yNode ? 'top' : 'bottom'
        } else {
          labelPosition = 'bottom'
        }
      }
    }

    if (photoUrl) {
      // 1. Push border ring node (bottom layer)
      echartsNodes.push({
        id: `border-${mid}`,
        x: x,
        y: y,
        symbol: 'circle',
        symbolSize: mid === centerId ? 48 : 36,
        itemStyle: {
          color: 'none',
          borderColor: isActive ? '#c48b58' : (isDeceased ? '#666666' : color),
          borderWidth: isActive ? 3 : (isDeceased ? 2 : 1.5),
          shadowColor: isActive ? '#c48b58' : 'rgba(0,0,0,0.15)',
          shadowBlur: isActive ? 10 : 6
        },
        silent: true
      })

      // 2. Push photo node with name label (middle layer)
      echartsNodes.push({
        id: String(mid),
        name: m.name,
        x: x,
        y: y,
        symbol: `image://${photoUrl}`,
        symbolSize: mid === centerId ? 42 : 30,
        label: {
          show: true,
          formatter: m.name,
          position: labelPosition,
          distance: 6,
          color: '#ffffff',
          fontSize: mid === centerId ? 11 : 9,
          fontWeight: mid === centerId ? 'bold' : 'normal',
          rotate: 0,
          textBorderColor: 'rgba(0,0,0,0.8)',
          textBorderWidth: 2.5
        },
        rawMember: m
      })

      // 3. Push deceased overlay if deceased (top layer)
      if (isDeceased) {
        echartsNodes.push({
          id: `deceased-${mid}`,
          x: x,
          y: y,
          symbol: 'circle',
          symbolSize: mid === centerId ? 42 : 30,
          itemStyle: {
            color: 'rgba(128, 128, 128, 0.4)',
            decal: {
              symbol: 'line',
              dashArrayX: [1, 0],
              dashArrayY: [2, 5],
              rotation: 45,
              color: 'rgba(0, 0, 0, 0.25)'
            }
          },
          silent: true
        })
      }
    } else {
      // Standard node without photo (clean colored circle)
      echartsNodes.push({
        id: String(mid),
        name: m.name,
        x: x,
        y: y,
        symbol: 'circle',
        symbolSize: mid === centerId ? 42 : 30,
        itemStyle: {
          color: isDeceased ? '#a0a0a0' : color,
          borderColor: isActive ? '#c48b58' : (isDeceased ? '#666666' : '#ffffff'),
          borderWidth: isActive ? 3 : (isDeceased ? 2 : 1.5),
          shadowColor: isActive ? '#c48b58' : 'rgba(0,0,0,0.15)',
          shadowBlur: isActive ? 10 : 6,
          decal: isDeceased ? {
            symbol: 'line',
            dashArrayX: [1, 0],
            dashArrayY: [2, 5],
            rotation: 45,
            color: 'rgba(0, 0, 0, 0.2)'
          } : undefined
        },
        label: {
          show: true,
          formatter: m.name,
          position: labelPosition,
          distance: 6,
          color: '#ffffff',
          fontSize: mid === centerId ? 11 : 9,
          fontWeight: mid === centerId ? 'bold' : 'normal',
          rotate: 0,
          textBorderColor: 'rgba(0,0,0,0.8)',
          textBorderWidth: 2.5
        },
        rawMember: m
      })
    }
  }

  // Draw links
  const processedCouples = new Set()
  for (const m of members) {
    const mid = Number(m.id)
    if (!coords.has(mid)) continue
    
    // 1. Spouses (Red Lines)
    if (Array.isArray(m.spouseIds)) {
      for (const sid of m.spouseIds) {
        if (!coords.has(sid)) continue
        const coupleKey = [mid, sid].sort().join('-')
        if (processedCouples.has(coupleKey)) continue
        processedCouples.add(coupleKey)

        const c1 = coords.get(mid)
        const c2 = coords.get(sid)
        
        let diff = c2.thetaDegrees - c1.thetaDegrees
        if (diff > 180) diff -= 360
        if (diff < -180) diff += 360
        
        const spouseCurveness = -Math.sign(diff) * 0.18

        echartsLinks.push({
          source: String(mid),
          target: String(sid),
          lineStyle: {
            color: '#ff4d4d',
            width: 3,
            curveness: spouseCurveness
          }
        })

        const childrenOfCouple = members.filter(c => 
          (c.fatherId === mid && c.motherId === sid) || 
          (c.fatherId === sid && c.motherId === mid)
        )

        if (childrenOfCouple.length > 0) {
          const deltaThetaRad = Math.abs(diff) * Math.PI / 180
          
          // Calculate rMid to lie exactly on the curved spouse arc
          const rMid = ((c1.r + c2.r) / 2) * (Math.cos(deltaThetaRad / 2) + Math.abs(spouseCurveness) * Math.sin(deltaThetaRad / 2))
          
          // Use vector average for thetaMid to avoid wrap-around issues
          const sumCos = Math.cos(c1.thetaDegrees * Math.PI / 180) + Math.cos(c2.thetaDegrees * Math.PI / 180)
          const sumSin = Math.sin(c1.thetaDegrees * Math.PI / 180) + Math.sin(c2.thetaDegrees * Math.PI / 180)
          let thetaMid = Math.atan2(sumSin, sumCos) * 180 / Math.PI
          thetaMid = ((thetaMid % 360) + 360) % 360

          const isCenterCouple = (mid === Number(centerId) || sid === Number(centerId))

          const thetaMidRad = thetaMid * Math.PI / 180
          const xMid = rMid * Math.cos(thetaMidRad)
          const yMid = -rMid * Math.sin(thetaMidRad)

          const virtualNodeId = `midpoint-${coupleKey}`
          echartsNodes.push({
            id: virtualNodeId,
            x: xMid,
            y: yMid,
            symbolSize: 0,
            itemStyle: { opacity: 0 },
            label: { show: false }
          })

          const parentSourceId = isCenterCouple ? String(centerId) : virtualNodeId

          const closeChildren = []
          for (const child of childrenOfCouple) {
            const childId = Number(child.id)
            if (!coords.has(childId)) continue

            const cChild = coords.get(childId)
            const isDistant = !isCenterCouple && (Math.abs(cChild.r - rMid) > RingWidth * 1.5 || Math.abs(cChild.thetaDegrees - thetaMid) > 60)

            if (isDistant) {
              const shortcutNodeId = `shortcut-${coupleKey}-${childId}`
              const shortcutR = rMid + 30
              const shortcutTheta = thetaMid

              const shortcutThetaRad = shortcutTheta * Math.PI / 180
              const xShortcut = shortcutR * Math.cos(shortcutThetaRad)
              const yShortcut = -shortcutR * Math.sin(shortcutThetaRad)

              echartsNodes.push({
                id: shortcutNodeId,
                x: xShortcut,
                y: yShortcut,
                symbol: 'pin',
                symbolSize: 10,
                itemStyle: { color: '#4d7cff' },
                label: {
                  show: true,
                  formatter: `→ To ${child.name}`,
                  position: 'right',
                  color: '#4d7cff',
                  fontSize: 10,
                  textBorderColor: 'rgba(0,0,0,0.8)',
                  textBorderWidth: 2
                }
              })

              echartsLinks.push({
                source: virtualNodeId,
                target: shortcutNodeId,
                lineStyle: {
                  color: '#4d7cff',
                  width: 1.5,
                  type: 'dashed'
                }
              })
            } else {
              closeChildren.push({ childId, childName: child.name, cChild })
            }
          }

          if (closeChildren.length > 0) {
            if (closeChildren.length === 1) {
              echartsLinks.push({
                source: parentSourceId,
                target: String(closeChildren[0].childId),
                lineStyle: {
                  color: '#4d7cff',
                  width: 2,
                  curveness: 0.05
                },
                symbol: ['none', 'arrow'],
                symbolSize: [0, 6]
              })
            } else {
              // Use vector average for avgTheta to avoid wrap-around issues
              const sumCos = closeChildren.reduce((sum, c) => sum + Math.cos(c.cChild.thetaDegrees * Math.PI / 180), 0)
              const sumSin = closeChildren.reduce((sum, c) => sum + Math.sin(c.cChild.thetaDegrees * Math.PI / 180), 0)
              let avgTheta = Math.atan2(sumSin, sumCos) * 180 / Math.PI
              avgTheta = ((avgTheta % 360) + 360) % 360

              // Place the bracket exactly halfway between the child ring and the immediate inner ring
              const rChild = closeChildren[0].cChild.r
              const rCC = rChild - RingWidth / 2
              const avgThetaRad = avgTheta * Math.PI / 180
              const xCC = rCC * Math.cos(avgThetaRad)
              const yCC = -rCC * Math.sin(avgThetaRad)

              const ccNodeId = `cc-${coupleKey}`
              echartsNodes.push({
                id: ccNodeId,
                x: xCC,
                y: yCC,
                symbolSize: 0,
                itemStyle: { opacity: 0 },
                label: { show: false }
              })

              echartsLinks.push({
                source: parentSourceId,
                target: ccNodeId,
                lineStyle: {
                  color: '#4d7cff',
                  width: 2
                }
              })

              for (const cc of closeChildren) {
                let diff = cc.cChild.thetaDegrees - avgTheta
                if (diff > 180) diff -= 360
                if (diff < -180) diff += 360
                const curveness = Math.sin(diff * Math.PI / 180) * 0.2

                echartsLinks.push({
                  source: ccNodeId,
                  target: String(cc.childId),
                  lineStyle: {
                    color: '#4d7cff',
                    width: 2,
                    curveness: curveness
                  },
                  symbol: ['none', 'arrow'],
                  symbolSize: [0, 6]
                })
              }
            }
          }
        }
      }
    }

    // 2. Single Parent (Blue Lines)
    const childrenOfSingleParent = members.filter(c => {
      const isFatherChild = c.fatherId === mid && (!c.motherId || !Array.isArray(m.spouseIds) || !m.spouseIds.includes(c.motherId))
      const isMotherChild = c.motherId === mid && (!c.fatherId || !Array.isArray(m.spouseIds) || !m.spouseIds.includes(c.fatherId))
      return isFatherChild || isMotherChild
    })

    if (childrenOfSingleParent.length > 0) {
      const cParent = coords.get(mid)
      const isCenterParent = (mid === Number(centerId))
      const closeSingleChildren = []

      for (const child of childrenOfSingleParent) {
        const childId = Number(child.id)
        if (!coords.has(childId)) continue
        
        const cChild = coords.get(childId)
        const isDistant = !isCenterParent && (Math.abs(cChild.r - cParent.r) > RingWidth * 1.5 || Math.abs(cChild.thetaDegrees - cParent.thetaDegrees) > 60)

        if (isDistant) {
          const shortcutNodeId = `shortcut-single-${mid}-${childId}`
          const shortcutR = cParent.r + 30
          const shortcutTheta = cParent.thetaDegrees

          const shortcutThetaRad = shortcutTheta * Math.PI / 180
          const xShortcut = shortcutR * Math.cos(shortcutThetaRad)
          const yShortcut = -shortcutR * Math.sin(shortcutThetaRad)

          echartsNodes.push({
            id: shortcutNodeId,
            x: xShortcut,
            y: yShortcut,
            symbol: 'pin',
            symbolSize: 10,
            itemStyle: { color: '#4d7cff' },
            label: {
              show: true,
              formatter: `→ To ${child.name}`,
              position: 'right',
              color: '#4d7cff',
              fontSize: 10,
              textBorderColor: 'rgba(0,0,0,0.8)',
              textBorderWidth: 2
            }
          })

          echartsLinks.push({
            source: String(mid),
            target: shortcutNodeId,
            lineStyle: {
              color: '#4d7cff',
              width: 1.5,
              type: 'dashed'
            }
          })
        } else {
          closeSingleChildren.push({ childId, childName: child.name, cChild })
        }
      }

      if (closeSingleChildren.length > 0) {
        if (closeSingleChildren.length === 1) {
          echartsLinks.push({
            source: String(mid),
            target: String(closeSingleChildren[0].childId),
            lineStyle: {
              color: '#4d7cff',
              width: 2,
              curveness: 0.05
            },
            symbol: ['none', 'arrow'],
            symbolSize: [0, 6]
          })
        } else {
          // Use vector average for avgTheta to avoid wrap-around issues
          const sumCos = closeSingleChildren.reduce((sum, c) => sum + Math.cos(c.cChild.thetaDegrees * Math.PI / 180), 0)
          const sumSin = closeSingleChildren.reduce((sum, c) => sum + Math.sin(c.cChild.thetaDegrees * Math.PI / 180), 0)
          let avgTheta = Math.atan2(sumSin, sumCos) * 180 / Math.PI
          avgTheta = ((avgTheta % 360) + 360) % 360

          // Place the bracket exactly halfway between the child ring and the parent ring
          const rChild = closeSingleChildren[0].cChild.r
          const rCC = rChild - RingWidth / 2
          const avgThetaRad = avgTheta * Math.PI / 180
          const xCC = rCC * Math.cos(avgThetaRad)
          const yCC = -rCC * Math.sin(avgThetaRad)

          const ccNodeId = `cc-single-${mid}`
          echartsNodes.push({
            id: ccNodeId,
            x: xCC,
            y: yCC,
            symbolSize: 0,
            itemStyle: { opacity: 0 },
            label: { show: false }
          })

          echartsLinks.push({
            source: String(mid),
            target: ccNodeId,
            lineStyle: {
              color: '#4d7cff',
              width: 2
            }
          })

          for (const cc of closeSingleChildren) {
            let diff = cc.cChild.thetaDegrees - avgTheta
            if (diff > 180) diff -= 360
            if (diff < -180) diff += 360
            const curveness = Math.sin(diff * Math.PI / 180) * 0.2

            echartsLinks.push({
              source: ccNodeId,
              target: String(cc.childId),
              lineStyle: {
                color: '#4d7cff',
                width: 2,
                curveness: curveness
              },
              symbol: ['none', 'arrow'],
              symbolSize: [0, 6]
            })
          }
        }
      }
    }
  }

  // Handle search keywords
  const keyword = normalizeText(searchKeyword.value).toLowerCase()
  const isSearchActive = !!keyword
  if (isSearchActive) {
    for (const node of echartsNodes) {
      if (node.symbolSize === 0 || node.id.startsWith('ring-') || node.id.startsWith('border-') || node.id.startsWith('deceased-')) continue
      const m = node.rawMember
      if (!m) continue
      const spouseNames = (m.spouses || []).map(s => s.name).filter(Boolean).join('、') || m.spouse || ''
      const searchHaystack = [
        m.name,
        m.branch,
        m.generationName,
        m.rankTitle,
        spouseNames,
        m.birthPlace,
        m.residence
      ].filter(Boolean).join(' ').toLowerCase()
      
      const matches = searchHaystack.includes(keyword)
      if (matches) {
        node.itemStyle = node.itemStyle || {}
        node.itemStyle.opacity = 1.0
        node.itemStyle.borderColor = '#d3a26a'
        node.itemStyle.borderWidth = 3
        node.label = node.label || {}
        node.label.fontWeight = 'bold'

        // Highlight matching border node if it exists
        const borderNode = echartsNodes.find(n => n.id === `border-${node.id}`)
        if (borderNode) {
          borderNode.itemStyle.opacity = 1.0
          borderNode.itemStyle.borderColor = '#d3a26a'
          borderNode.itemStyle.borderWidth = 3
        }
      } else {
        node.itemStyle = node.itemStyle || {}
        node.itemStyle.opacity = 0.15
        node.label = node.label || {}
        node.label.opacity = 0.15

        // Dim associated border/deceased nodes
        const borderNode = echartsNodes.find(n => n.id === `border-${node.id}`)
        if (borderNode) borderNode.itemStyle.opacity = 0.15
        const deceasedNode = echartsNodes.find(n => n.id === `deceased-${node.id}`)
        if (deceasedNode) deceasedNode.itemStyle.opacity = 0.15
      }
    }

    for (const link of echartsLinks) {
      const sourceNode = echartsNodes.find(n => n.id === link.source)
      const targetNode = echartsNodes.find(n => n.id === link.target)
      const sourceDimmed = sourceNode && sourceNode.itemStyle && sourceNode.itemStyle.opacity === 0.15
      const targetDimmed = targetNode && targetNode.itemStyle && targetNode.itemStyle.opacity === 0.15
      if (sourceDimmed || targetDimmed) {
        link.lineStyle = { ...link.lineStyle, opacity: 0.08 }
      }
    }
  }

  // Add background helper rings (concentric circles)
  for (let i = 1; i <= maxDistance; i++) {
    echartsNodes.push({
      id: `ring-${i}`,
      x: 0,
      y: 0,
      symbol: 'circle',
      symbolSize: i * RingWidth * 2,
      itemStyle: {
        color: 'none',
        borderColor: 'rgba(211, 162, 106, 0.15)',
        borderWidth: 1,
        borderType: 'dashed'
      },
      silent: true
    })
  }

  return { nodes: echartsNodes, links: echartsLinks, maxDistance }
}

function renderChart() {
  if (!chartInstance) return
  
  if (!currentCenterMemberId.value && props.members.length > 0) {
    currentCenterMemberId.value = findDefaultCenterMember()
  }
  
  const focusId = currentCenterMemberId.value
  if (!focusId) return

  const layoutData = computeLayout(props.members, focusId)
  const maxDistance = layoutData.maxDistance || 1

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(30, 25, 20, 0.95)',
      borderColor: '#d3a26a',
      borderWidth: 1,
      textStyle: {
        color: '#ffffff'
      },
      formatter: (params) => {
        const data = params.data?.rawMember
        if (!data) return ''
        const genderColor = data.gender === '女' ? '#ff85a2' : '#85a2ff'
        const spouse = (data.spouses || []).map(s => s.name).filter(Boolean).join('、') || data.spouse || '无'
        const lifespan = `${data.birthDate || data.birthDateText || '生年不详'}${data.deathDate || data.deathDateText ? ' ~ ' + (data.deathDate || data.deathDateText) : ''}`
        return `
          <div style="padding: 6px; font-family: system-ui, sans-serif; line-height: 1.6;">
            <div style="font-size: 15px; font-weight: bold; margin-bottom: 4px; border-bottom: 1px solid rgba(211,162,106,0.3); padding-bottom: 4px; display: flex; align-items: center; justify-content: space-between; gap: 20px;">
              <span>${data.name}</span>
              <span style="font-size: 11px; color: ${genderColor}; background: ${genderColor}18; padding: 1px 4px; border-radius: 3px; border: 1px solid ${genderColor}33;">
                ${data.gender || '未知'}
              </span>
            </div>
            <div style="font-size: 12px;">
              <div><strong>世代：</strong>第 ${data.generation} 代 ${data.generationName ? `(${data.generationName}辈)` : ''}</div>
              <div><strong>排行：</strong>${data.rankTitle || '无'}</div>
              <div><strong>支系：</strong>${data.branch || '主脉'}</div>
              <div><strong>生卒：</strong>${lifespan}</div>
              <div><strong>配偶：</strong>${spouse}</div>
              <div style="margin-top: 4px; font-size: 10px; color: rgba(255,255,255,0.5); border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 4px;">
                双击可将该成员设为关系圈中心
              </div>
            </div>
          </div>
        `
      }
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        data: layoutData.nodes,
        links: layoutData.links,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: [0, 6],
        itemStyle: {
          borderWidth: 1.5,
          borderColor: '#ffffff'
        },
        lineStyle: {
          width: 2,
          opacity: 0.8
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: {
            width: 4
          }
        }
      }
    ]
  }
  chartInstance.setOption(option)
}

function goBackCenter() {
  if (centerHistoryStack.value.length > 0) {
    currentCenterMemberId.value = centerHistoryStack.value.pop()
    renderChart()
  }
}

function resetToAncestor() {
  const ancestorId = findDefaultCenterMember()
  if (ancestorId && currentCenterMemberId.value !== ancestorId) {
    centerHistoryStack.value.push(currentCenterMemberId.value)
    currentCenterMemberId.value = ancestorId
    renderChart()
  }
}

function setCenterMember(memberId) {
  if (!memberId) return
  const idValue = isNaN(Number(memberId)) ? memberId : Number(memberId)
  if (currentCenterMemberId.value !== idValue) {
    if (currentCenterMemberId.value) {
      centerHistoryStack.value.push(currentCenterMemberId.value)
    }
    currentCenterMemberId.value = idValue
    renderChart()
  }
}

defineExpose({
  setCenterMember
})

function resetSunburstView() {
  searchKeyword.value = ''
  generationLimit.value = '5'
  centerHistoryStack.value = []
  currentCenterMemberId.value = findDefaultCenterMember()
  renderChart()
}

function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (displayMode.value === 'flow') {
    nextTick(() => {
      initChart()
    })
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
  }
  clearMemberPhotos()
})

watch(displayMode, (newMode) => {
  if (newMode === 'flow') {
    nextTick(() => {
      initChart()
    })
  } else {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
  }
})

watch([() => props.tree, () => props.members], () => {
  if (displayMode.value === 'flow') {
    renderChart()
  }
}, { deep: true })

watch([searchKeyword, generationLimit], () => {
  if (displayMode.value === 'flow') {
    renderChart()
  }
})

const modeLabel = computed(() => ({ reader: '族谱阅读', flow: '全景关系图' }[displayMode.value] || '族谱阅读'))
const memberCount = computed(() => (props.members || []).length || readerItems.value.length)
const generationCount = computed(() => new Set((readerItems.value || []).map(item => item.generation).filter(g => g !== null && g !== undefined)).size)
const currentFocusMemberId = computed(() => localFocusMemberId.value ?? props.activeMemberId)

function nodeKey(node) {
  return String(node?.id ?? node?.name ?? '')
}

function toNumber(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function normalizeText(value) {
  return String(value || '').trim()
}

function relationFatherId(member) {
  return member?.fatherId ?? member?.father_id ?? null
}

function relationMotherId(member) {
  return member?.motherId ?? member?.mother_id ?? null
}

function relationParentIds(member) {
  return [relationFatherId(member), relationMotherId(member)]
}

function privacyLabel(level) {
  return { public: '公开', login: '登录可见', branch: '本分支可见', admin: '仅管理员可见' }[level] || '公开'
}

function sortByGenealogy(a, b) {
  const gA = a?.generation ?? a?.generationNo
  const gB = b?.generation ?? b?.generationNo
  const rA = a?.rankNo ?? a?.rank_no
  const rB = b?.rankNo ?? b?.rank_no
  return (Number(gA !== null && gA !== undefined ? gA : 999) - Number(gB !== null && gB !== undefined ? gB : 999))
    || (Number(rA !== null && rA !== undefined ? rA : 999) - Number(rB !== null && rB !== undefined ? rB : 999))
    || String(a?.name || '').localeCompare(String(b?.name || ''), 'zh-Hans-CN')
}

function descendantCount(node) {
  let total = 0
  for (const child of (node?.children || [])) total += 1 + descendantCount(child)
  return total
}

function computeMainLineIds(roots) {
  const ids = new Set()
  function walk(node) {
    if (!node) return
    ids.add(nodeKey(node))
    const children = [...(node.children || [])].sort(sortByGenealogy)
    if (children.length) walk(children[0])
  }
  for (const root of (roots || [])) walk(root)
  return ids
}

const memberById = computed(() => {
  const map = new Map()
  for (const member of props.members || []) {
    const id = toNumber(member?.id)
    if (id !== null) map.set(id, member)
  }
  for (const item of readerItems.value || []) {
    const id = toNumber(item.id)
    if (id !== null && !map.has(id)) map.set(id, item.node)
  }
  return map
})

const readerItems = computed(() => {
  const items = []
  const seen = new Set()
  const mainIds = computeMainLineIds(props.tree || [])
  const majorBranchIndexMap = new Map()
  const roots = [...(props.tree || [])].sort(sortByGenealogy)
  const palette = branchPalette.value

  const rootsMinGen = roots.length ? Math.min(...roots.map(root => {
    const gen = root?.generation ?? root?.generationNo;
    return gen !== null && gen !== undefined ? Number(gen) : 1;
  })) : 1
  const branchGen = rootsMinGen <= 1 ? 2 : rootsMinGen + 1

  function getGeneration(node, depth) {
    const gen = node?.generation ?? node?.generationNo;
    return gen !== null && gen !== undefined ? Number(gen) : (depth || 1);
  }

  function getBranchInfo(node, branchNode, rootIndex) {
    const familySurname = getFamilySurname(props.familyName)
    const familyBaseHue = getBaseHueForSurname(familySurname)
    if (!branchNode) {
      return { key: 'main', label: '主源', index: rootIndex, color: `hsl(${familyBaseHue}, 16%, 60%)` }
    }
    const key = nodeKey(branchNode)
    if (!majorBranchIndexMap.has(key)) {
      majorBranchIndexMap.set(key, majorBranchIndexMap.size)
    }
    const index = majorBranchIndexMap.get(key)
    const color = palette[index % palette.length]
    const label = branchNode.branch || `${branchNode.name || `${index + 1}房`}支`
    return { key: `branch-${key}`, label, index, color }
  }

  function walk(node, parent, depth, branchNode, rootIndex, branchGen) {
    const id = nodeKey(node)
    if (!id || seen.has(id)) return
    seen.add(id)
    const gen = getGeneration(node, depth)
    let currentBranchNode = branchNode
    if (gen === branchGen) {
      currentBranchNode = node
    }
    const branchInfo = getBranchInfo(node, currentBranchNode, rootIndex)
    const children = [...(node.children || [])].sort(sortByGenealogy)
    const relationChildren = relationChildrenOf(id)
    const relationDescendants = relationDescendantCount(id)
    const spouseNames = (node.spouses || []).map(sp => sp?.name).filter(Boolean).join('、') || node.spouse || ''
    const searchHaystack = [node.name, node.branch, node.generationName, node.rankTitle, spouseNames, node.birthPlace, node.residence].filter(Boolean).join(' ')
    items.push({
      id,
      node,
      parentId: parent ? nodeKey(parent) : null,
      name: node.name || '未命名成员',
      gender: node.gender,
      generation: gen,
      generationName: node.generationName,
      rankNo: node.rankNo,
      rankTitle: node.rankTitle,
      branch: node.branch,
      branchKey: branchInfo.key,
      branchLabel: branchInfo.label === '主源' ? '' : branchInfo.label,
      branchColor: branchInfo.color,
      branchIndex: branchInfo.index,
      spouseNames,
      childCount: Math.max(children.length, relationChildren.length),
      descendantCount: Math.max(descendantCount(node), relationDescendants),
      birthDate: node.birthDate || node.birthDateText,
      deathDate: node.deathDate || node.deathDateText,
      privacyLevel: node.privacyLevel,
      privacyLabel: node.privacyLabel || privacyLabel(node.privacyLevel),
      visibilityScope: node.visibilityScope || 'full',
      visibilityLabel: node.visibilityLabel || '',
      hasSource: Boolean(normalizeText(node.source)),
      isMainLine: mainIds.has(id),
      searchHaystack,
      matchesSearch: false,
    })
    children.forEach(child => walk(child, node, gen + 1, currentBranchNode, rootIndex, branchGen))
  }

  roots.forEach((root, rootIndex) => {
    walk(root, null, getGeneration(root, 1), null, rootIndex, branchGen)
  })

  const itemById = new Map()
  for (const item of items) {
    const itemId = toNumber(item.id)
    if (itemId !== null) itemById.set(itemId, item)
  }
  const rawMemberById = new Map()
  for (const member of props.members || []) {
    const memberId = toNumber(member?.id)
    if (memberId !== null) rawMemberById.set(memberId, member)
  }

  function spouseNamesFromMember(member) {
    if (normalizeText(member?.spouse)) return member.spouse
    const names = []
    const spouseIds = Array.isArray(member?.spouseIds) ? member.spouseIds : []
    for (const spouseId of spouseIds) {
      const spouse = rawMemberById.get(toNumber(spouseId))
      if (spouse?.name) names.push(spouse.name)
    }
    return names.join('、')
  }

  function addRelationSupplement(member, parentItem) {
    const id = nodeKey(member)
    if (!id || seen.has(id)) return null
    seen.add(id)
    const memberId = toNumber(member.id)
    const relationChildren = relationChildrenOf(member.id)
    const relationDescendants = relationDescendantCount(member.id)
    const spouseNames = spouseNamesFromMember(member)
    const searchHaystack = [member.name, member.branch, member.generationName, member.rankTitle, spouseNames, member.birthPlace, member.residence].filter(Boolean).join(' ')
    const item = {
      id,
      node: member,
      parentId: parentItem ? String(parentItem.id) : null,
      name: member.name || '未命名成员',
      gender: member.gender,
      generation: member.generation !== null && member.generation !== undefined ? Number(member.generation) : (parentItem?.generation !== null && parentItem?.generation !== undefined ? Number(parentItem.generation) + 1 : 1),
      generationName: member.generationName,
      rankNo: member.rankNo,
      rankTitle: member.rankTitle,
      branch: member.branch,
      branchKey: parentItem?.branchKey || 'main',
      branchLabel: parentItem?.branchLabel || member.branch || '',
      branchColor: parentItem?.branchColor || palette[0],
      branchIndex: parentItem?.branchIndex ?? 0,
      spouseNames,
      childCount: relationChildren.length,
      descendantCount: relationDescendants,
      birthDate: member.birthDate || member.birthDateText,
      deathDate: member.deathDate || member.deathDateText,
      privacyLevel: member.privacyLevel,
      privacyLabel: member.privacyLabel || privacyLabel(member.privacyLevel),
      hasSource: Boolean(normalizeText(member.source)),
      isMainLine: parentItem?.isMainLine || false,
      isRelationSupplement: true,
      visibilityScope: member.visibilityScope || 'full',
      visibilityLabel: member.visibilityLabel || '',
      searchHaystack,
      matchesSearch: false,
    }
    items.push(item)
    if (memberId !== null) itemById.set(memberId, item)
    return item
  }

  // `/tree` 为了避免配偶原生家庭重复，偏父系生成树；阅读模式仍要补全“母亲关系”能追到的子女。
  // 例如：孙永珍 -> 成小青、王文莲 -> 曹晓慧，这类子女挂在外姓配偶父系节点上时，后端树可能不会返回，
  // 这里按成员表 fatherId/motherId 关系递归补进阅读列表，并继承已显示父/母的分支归属。
  for (let pass = 0; pass < (props.members || []).length; pass += 1) {
    let changed = false
    for (const member of props.members || []) {
      const id = nodeKey(member)
      if (!id || seen.has(id)) continue
      const fatherItem = itemById.get(toNumber(relationFatherId(member)))
      const motherItem = itemById.get(toNumber(relationMotherId(member)))
      let parentItem = null
      if (fatherItem && motherItem) {
        const fatherIsSupp = fatherItem.isRelationSupplement
        const motherIsSupp = motherItem.isRelationSupplement
        if (fatherIsSupp && !motherIsSupp) {
          parentItem = motherItem
        } else if (!fatherIsSupp && motherIsSupp) {
          parentItem = fatherItem
        } else {
          const fatherIsMain = fatherItem.branchKey === 'main'
          const motherIsMain = motherItem.branchKey === 'main'
          if (fatherIsMain && !motherIsMain) {
            parentItem = motherItem
          } else if (!fatherIsMain && motherIsMain) {
            parentItem = fatherItem
          } else {
            parentItem = fatherItem || motherItem
          }
        }
      } else {
        parentItem = fatherItem || motherItem
      }
      if (!parentItem) continue
      if (addRelationSupplement(member, parentItem)) changed = true
    }
    if (!changed) break
  }

  // Lineage-based sorting to ensure perfect depth-first genealogical order
  const memberMap = new Map()
  for (const item of items) {
    memberMap.set(item.id, item)
  }
  
  function getLineagePath(itemId) {
    const path = []
    let currId = itemId
    const visited = new Set()
    while (currId && !visited.has(currId)) {
      visited.add(currId)
      path.unshift(currId)
      const item = memberMap.get(currId)
      currId = item?.parentId || null
    }
    return path
  }
  
  const pathMap = new Map()
  for (const item of items) {
    pathMap.set(item.id, getLineagePath(item.id))
  }
  
  function compareLineage(a, b) {
    const pathA = pathMap.get(a.id) || []
    const pathB = pathMap.get(b.id) || []
    const minLen = Math.min(pathA.length, pathB.length)
    for (let i = 0; i < minLen; i++) {
      if (pathA[i] !== pathB[i]) {
        const ancA = memberMap.get(pathA[i])
        const ancB = memberMap.get(pathB[i])
        const rA = ancA?.rankNo ?? ancA?.rank_no
        const rB = ancB?.rankNo ?? ancB?.rank_no
        const rankA = (rA !== null && rA !== undefined && rA !== '') ? Number(rA) : 999
        const rankB = (rB !== null && rB !== undefined && rB !== '') ? Number(rB) : 999
        if (rankA !== rankB) return rankA - rankB
        return String(ancA?.name || '').localeCompare(String(ancB?.name || ''), 'zh-Hans-CN')
      }
    }
    return pathA.length - pathB.length
  }

  return items.sort(compareLineage)
})

const branchOptions = computed(() => {
  const map = new Map()
  for (const item of readerItems.value) {
    if (!map.has(item.branchKey)) {
      map.set(item.branchKey, {
        key: item.branchKey,
        label: item.branchKey === 'main' ? '主源' : (item.branchLabel || '未分支'),
        color: item.branchColor,
        index: item.branchKey === 'main' ? -1 : (item.branchIndex ?? 0),
        count: 0,
      })
    }
    map.get(item.branchKey).count += 1
  }
  const branches = [...map.values()].sort((a, b) => a.index - b.index)
  return [{ key: 'all', label: '全部分支', color: '#8b7154', count: readerItems.value.length }, ...branches]
})

const minGeneration = computed(() => {
  const gens = readerItems.value.map(item => item.generation).filter(g => g !== null && g !== undefined && !isNaN(g))
  return gens.length ? Math.min(...gens) : 1
})

const childrenByParentId = computed(() => {
  const map = new Map()
  for (const member of props.members || []) {
    for (const parentId of relationParentIds(member)) {
      const pid = toNumber(parentId)
      if (pid === null) continue
      if (!map.has(pid)) map.set(pid, [])
      map.get(pid).push(member)
    }
  }
  return map
})

function relationChildrenOf(memberId) {
  const id = toNumber(memberId)
  if (id === null) return []
  return [...(childrenByParentId.value.get(id) || [])].sort(sortByGenealogy)
}

function relationDescendantCount(memberId, seen = new Set()) {
  const id = toNumber(memberId)
  if (id === null || seen.has(id)) return 0
  seen.add(id)
  let total = 0
  for (const child of childrenByParentId.value.get(id) || []) {
    const childId = toNumber(child?.id)
    if (childId === null || seen.has(childId)) continue
    total += 1 + relationDescendantCount(childId, seen)
  }
  return total
}

function memberFromLookup(id) {
  const n = toNumber(id)
  return n === null ? null : memberById.value.get(n) || null
}

function addAncestorsToScope(member, scopeIds) {
  if (!member) return
  for (const parentId of relationParentIds(member)) {
    const pid = toNumber(parentId)
    if (pid === null || scopeIds.has(pid)) continue
    scopeIds.add(pid)
    addAncestorsToScope(memberFromLookup(pid), scopeIds)
  }
}

function addDescendantsToScope(memberId, scopeIds) {
  const id = toNumber(memberId)
  if (id === null) return
  for (const child of childrenByParentId.value.get(id) || []) {
    const childId = toNumber(child?.id)
    if (childId === null || scopeIds.has(childId)) continue
    scopeIds.add(childId)
    addDescendantsToScope(childId, scopeIds)
  }
}

const branchScopedItemIds = computed(() => {
  if (branchFilter.value === 'all') return null

  if (branchFilter.value === 'main') {
    return new Set(readerItems.value.filter(item => item.branchKey === 'main').map(item => toNumber(item.id)).filter(id => id !== null))
  }

  const branchItems = readerItems.value
    .filter(item => item.branchKey === branchFilter.value)
    .sort(sortByGenealogy)
  const branchRoot = branchItems[0]
  if (!branchRoot) return new Set()

  const scopeIds = new Set()
  for (const item of branchItems) {
    const itemId = toNumber(item.id)
    if (itemId !== null) scopeIds.add(itemId)
  }

  const rootId = toNumber(branchRoot.id)
  if (rootId !== null) {
    scopeIds.add(rootId)
    const rootMember = memberFromLookup(rootId) || branchRoot.node
    addAncestorsToScope(rootMember, scopeIds)
  }

  // 分支阅读不能只按父系树节点裁剪：女性成员作为母亲记录的子女，也应纳入本支脉。
  for (const item of branchItems) {
    addDescendantsToScope(item.id, scopeIds)
  }

  return scopeIds
})

const visibleReaderItems = computed(() => {
  const keyword = normalizeText(searchKeyword.value).toLowerCase()
  const limit = generationLimit.value === 'all' ? Infinity : Number(generationLimit.value || 5)
  const maxGeneration = Number.isFinite(limit) ? minGeneration.value + limit - 1 : Infinity
  const scopedIds = branchScopedItemIds.value
  return readerItems.value
    .filter((item) => scopedIds === null || scopedIds.has(toNumber(item.id)))
    .filter((item) => item.generation <= maxGeneration)
    .filter((item) => {
      if (!keyword) return true
      return String(item.searchHaystack || '').toLowerCase().includes(keyword)
    })
    .map((item) => ({ ...item, matchesSearch: Boolean(keyword) }))
})

const generationColumns = computed(() => {
  const map = new Map()
  const indexMap = new Map()
  readerItems.value.forEach((item, index) => {
    indexMap.set(item.id, index)
  })
  for (const item of visibleReaderItems.value) {
    if (!map.has(item.generation)) map.set(item.generation, [])
    map.get(item.generation).push(item)
  }
  return [...map.entries()].sort((a, b) => a[0] - b[0]).map(([generation, items]) => {
    const sortedItems = [...items].sort((a, b) => {
      const idxA = indexMap.get(a.id) ?? 999999
      const idxB = indexMap.get(b.id) ?? 999999
      return idxA - idxB
    })
    return { generation, items: sortedItems }
  })
})

const summaryMember = computed(() => {
  const id = toNumber(currentFocusMemberId.value)
  if (id !== null && memberById.value.has(id)) return memberById.value.get(id)
  return visibleReaderItems.value[0]?.node || null
})
const focusMember = computed(() => summaryMember.value)

function getMember(id) {
  const n = toNumber(id)
  return n === null ? null : memberById.value.get(n) || null
}

const focusSpouses = computed(() => {
  const m = focusMember.value
  if (!m) return []
  const result = []
  const seen = new Set()
  const ids = Array.isArray(m.spouseIds) ? m.spouseIds : []
  for (const sid of ids) {
    const sp = getMember(sid)
    if (sp?.id && !seen.has(Number(sp.id))) {
      result.push(sp)
      seen.add(Number(sp.id))
    }
  }
  const nodeItem = readerItems.value.find(item => Number(item.id) === Number(m.id))
  for (const sp of nodeItem?.node?.spouses || []) {
    if (sp?.id) {
      const full = getMember(sp.id) || sp
      if (!seen.has(Number(sp.id))) {
        result.push(full)
        seen.add(Number(sp.id))
      }
    } else if (sp?.name && !result.some(item => item.name === sp.name)) {
      result.push({ name: sp.name })
    }
  }
  if (!result.length && normalizeText(m.spouse)) {
    result.push(...normalizeText(m.spouse).split(/[、,，/\s]+/).filter(Boolean).map(name => ({ name })))
  }
  return result
})

const focusChildren = computed(() => {
  const m = focusMember.value
  if (!m?.id) return []
  const id = Number(m.id)
  const children = relationChildrenOf(id)
  if (children.length) return children
  const item = readerItems.value.find(row => Number(row.id) === id)
  return [...(item?.node?.children || [])].sort(sortByGenealogy)
})

const summarySpouseText = computed(() => focusSpouses.value.map(sp => sp.name).filter(Boolean).join('、'))

function setLocalFocus(id) {
  const n = toNumber(id)
  localFocusMemberId.value = n !== null ? n : id
}

function firstMemberForBranch(branchKey) {
  const candidates = readerItems.value
    .filter((item) => branchKey === 'all' ? true : item.branchKey === branchKey)
    .sort(sortByGenealogy)
  return candidates[0] || visibleReaderItems.value[0] || null
}

function setBranchFilter(branchKey) {
  branchFilter.value = branchKey
  const first = firstMemberForBranch(branchKey)
  if (first?.id) setLocalFocus(first.id)
}

function selectMember(id) {
  setLocalFocus(id)
  emit('node-click', id)
}

function resetReaderFilters() {
  searchKeyword.value = ''
  branchFilter.value = 'all'
  generationLimit.value = '5'
  const first = firstMemberForBranch('all')
  if (first?.id) setLocalFocus(first.id)
}

async function switchToFlowAndReset() {
  displayMode.value = 'flow'
}

watch(() => props.activeMemberId, (id) => {
  if (id) setLocalFocus(id)
  if (displayMode.value === 'flow') {
    renderChart()
  }
})

watch(branchOptions, (options) => {
  if (branchFilter.value !== 'all' && !options.some(option => option.key === branchFilter.value)) {
    setBranchFilter('all')
  }
})

watch(readerItems, (items) => {
  if (currentFocusMemberId.value || !items.length) return
  setLocalFocus(items[0].id)
}, { immediate: true })
</script>

<style scoped>
.tree-toolbar__summary {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tree-toolbar--lineage.lineage-toolbar-v2 {
  display: grid;
  grid-template-columns: minmax(240px, 0.95fr) minmax(420px, 1.25fr) auto;
  align-items: center;
}

.lineage-toolbar-v2__controls {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.lineage-search {
  width: 190px;
}

.generation-limit-select {
  width: 116px;
}

.tree-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.lineage-reader-shell {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr) 260px;
  gap: 12px;
  min-height: calc(100vh - 275px);
}

.lineage-branch-sidebar,
.lineage-focus-sidebar,
.lineage-reader-main,
.lineage-focus-main {
  border: 1px solid var(--border);
  border-radius: 18px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--card-bg) 96%, #fff), var(--card-bg));
}

.lineage-branch-sidebar,
.lineage-focus-sidebar {
  padding: 14px;
  overflow: auto;
  max-height: calc(100vh - 275px);
}

.sidebar-title {
  color: var(--text-main);
  font-weight: 700;
  margin-bottom: 10px;
}

.branch-filter-item {
  width: 100%;
  display: grid;
  grid-template-columns: 12px 1fr auto;
  align-items: center;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--text-main);
  text-align: left;
  padding: 9px 8px;
  cursor: pointer;
}

.branch-filter-item:hover,
.branch-filter-item.active {
  background: color-mix(in srgb, var(--primary) 8%, var(--card-bg));
  border-color: color-mix(in srgb, var(--primary) 22%, var(--border));
}

.branch-filter-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.branch-filter-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.branch-filter-item small {
  color: var(--text-secondary);
}

.lineage-reader-main,
.lineage-focus-main {
  padding: 14px;
  overflow: hidden;
}

.reader-status-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--primary) 8%, var(--card-bg));
}

.reader-status-bar b,
.reader-status-bar span {
  display: block;
}

.reader-status-bar b {
  color: var(--text-main);
  margin-bottom: 3px;
}

.reader-status-bar span {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.55;
}

.lineage-generation-board {
  display: flex;
  gap: 14px;
  overflow: auto;
  height: calc(100vh - 372px);
  padding-bottom: 8px;
}

.generation-column {
  min-width: 245px;
  max-width: 245px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.generation-column__header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: color-mix(in srgb, var(--card-bg) 82%, #fff);
  border: 1px solid var(--border);
  box-shadow: 0 8px 18px rgba(62,44,28,.05);
}

.generation-column__header strong {
  color: #6d3f1f;
}

.generation-column__header small {
  color: var(--text-secondary);
}

.generation-card-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reader-person-card {
  position: relative;
  border: 1px solid var(--border);
  border-left: 6px solid var(--branch-color, #c59b6b);
  border-radius: 18px;
  padding: 12px;
  background: linear-gradient(180deg, rgba(255,255,255,.94), rgba(255,250,241,.98));
  box-shadow: 0 10px 22px rgba(62,44,28,.07);
  cursor: pointer;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
  outline: none;
}

.reader-person-card:hover,
.reader-person-card:focus {
  transform: translateY(-2px);
  box-shadow: 0 14px 26px rgba(62,44,28,.12);
}

.reader-person-card.active {
  border-color: #c48b58;
  box-shadow: 0 0 0 3px rgba(196,139,88,.16), 0 14px 26px rgba(62,44,28,.12);
}

.reader-person-card.is-main-line::after {
  content: '';
  position: absolute;
  left: -6px;
  top: 12px;
  bottom: 12px;
  width: 6px;
  background: #6d3f1f;
  border-radius: 999px;
}

.reader-person-card.matches-search {
  background: linear-gradient(180deg, rgba(255,248,224,.98), rgba(255,250,241,.98));
}

.reader-person-card__top,
.reader-person-card__footer,
.focus-chip-row,
.summary-actions {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
}

.reader-person-card__top {
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 7px;
}

.reader-branch-pill,
.reader-main-pill,
.reader-relation-pill {
  border-radius: 999px;
  padding: 2px 7px;
  font-size: 11px;
}

.reader-branch-pill {
  color: #6d5038;
  background: color-mix(in srgb, var(--branch-color) 14%, #fff);
  border: 1px solid color-mix(in srgb, var(--branch-color) 45%, #fff);
}

.reader-main-pill {
  color: #8b4513;
  background: rgba(255,244,224,.9);
  border: 1px solid rgba(192,138,80,.32);
}

.reader-relation-pill,
.node-branch-pill.relation {
  color: #4f6785;
  background: rgba(230, 240, 252, .92);
  border: 1px solid rgba(107, 139, 181, .34);
}

.reader-person-card h3 {
  margin: 0 0 8px;
  color: var(--text-main);
  font-size: 19px;
  line-height: 1.25;
}

.reader-person-card__meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
}

.reader-person-card__relation {
  margin-top: 8px;
  padding-top: 7px;
  border-top: 1px dashed var(--border);
  color: var(--primary);
  font-size: 12px;
}

.reader-person-card__footer {
  margin-top: 9px;
  color: var(--text-secondary);
  font-size: 11px;
}

.reader-person-card__footer span {
  border-radius: 999px;
  background: color-mix(in srgb, var(--bg) 72%, #fff);
  padding: 2px 7px;
}

.reader-person-card__footer .has-source {
  color: #477b58;
  background: rgba(233, 247, 235, .92);
}

.reader-person-card__footer .missing-source {
  color: #b4782f;
  background: rgba(255, 247, 232, .92);
}

.focus-board {
  height: calc(100vh - 372px);
  overflow: auto;
  display: grid;
  gap: 14px;
  align-content: start;
}

.focus-row {
  border: 1px solid var(--border);
  border-radius: 18px;
  background: color-mix(in srgb, var(--card-bg) 88%, #fff);
  padding: 14px;
}

.focus-row h4 {
  margin: 0 0 10px;
  color: #6d3f1f;
}

.focus-card-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.focus-mini-card,
.focus-empty-card {
  min-width: 160px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--card-bg);
  padding: 11px 12px;
  text-align: left;
}

.focus-mini-card {
  cursor: pointer;
  color: var(--text-main);
}

.focus-mini-card:disabled {
  cursor: default;
  opacity: .78;
}

.focus-mini-card span,
.focus-mini-card small,
.focus-empty-card {
  color: var(--text-secondary);
  font-size: 12px;
}

.focus-mini-card b {
  display: block;
  margin: 5px 0;
  color: var(--text-main);
  font-size: 16px;
}

.focus-current-card {
  display: flex;
  gap: 14px;
  align-items: center;
  border-radius: 18px;
  padding: 16px;
  background: linear-gradient(135deg, rgba(255,248,232,.96), rgba(255,255,255,.9));
  border: 1px solid rgba(197, 155, 107, .32);
}

.focus-current-avatar,
.summary-avatar {
  width: 58px;
  height: 58px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  color: #fff;
  font-weight: 800;
  font-size: 24px;
  background: #9a6b3f;
  flex: none;
}

.focus-current-avatar.female,
.summary-avatar.female {
  background: #b06b6b;
}

.focus-current-card h3 {
  margin: 3px 0 5px;
  color: var(--text-main);
  font-size: 24px;
}

.focus-current-card p {
  margin: 0 0 8px;
  color: var(--text-secondary);
}

.summary-member-card {
  text-align: center;
}

.summary-avatar {
  margin: 4px auto 10px;
}

.summary-member-card h3 {
  margin: 0 0 4px;
  color: var(--text-main);
}

.summary-member-card p {
  margin: 0 0 12px;
  color: var(--text-secondary);
}

.summary-facts {
  display: grid;
  gap: 8px;
  text-align: left;
  margin-bottom: 12px;
}

.summary-facts div {
  border-radius: 12px;
  background: color-mix(in srgb, var(--bg) 74%, #fff);
  padding: 9px 10px;
}

.summary-facts span,
.summary-facts b {
  display: block;
}

.summary-facts span {
  color: var(--text-secondary);
  font-size: 12px;
  margin-bottom: 3px;
}

.summary-facts b {
  color: var(--text-main);
  font-size: 13px;
  line-height: 1.45;
}

.summary-actions {
  justify-content: center;
}

.tree-boundary-note {
  display: block;
  margin-top: 4px;
  color: #8b7154;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1280px) {
  .tree-toolbar--lineage.lineage-toolbar-v2 {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .lineage-toolbar-v2__controls,
  .tree-toolbar__actions {
    justify-content: flex-start;
  }

  .lineage-reader-shell {
    grid-template-columns: 170px minmax(0, 1fr);
  }

  .lineage-focus-sidebar {
    grid-column: 1 / -1;
    max-height: none;
  }
}

@media (max-width: 840px) {
  .lineage-reader-shell {
    grid-template-columns: 1fr;
  }

  .lineage-branch-sidebar,
  .lineage-focus-sidebar {
    max-height: none;
  }

  .lineage-generation-board,
  .focus-board {
    height: auto;
    max-height: none;
  }

  .generation-column {
    min-width: 230px;
  }
}

.tree-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 16px;
  background: linear-gradient(135deg, color-mix(in srgb, var(--card-bg) 94%, #fff), color-mix(in srgb, var(--bg) 68%, #fff));
}
.tree-wrap {
  border: 1px solid var(--border);
  border-radius: 18px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--card-bg) 95%, #fff), var(--card-bg));
  height: calc(100vh - 270px);
  overflow: hidden;
}
.tree-toolbar__eyebrow {
  font-size: 12px;
  letter-spacing: .12em;
  color: #9a6b3f;
}
.tree-toolbar__title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
}
.tree-toolbar__desc {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}
.tree-toolbar__legend {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.tree-toolbar__legend :deep(.el-tag) {
  border-radius: 999px;
}
.sunburst-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 720px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--card-bg) 96%, #fff), var(--card-bg));
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 16px;
  box-sizing: border-box;
  border: 1px solid var(--border);
  border-radius: 12px;
  margin-top: 12px;
}
.sunburst-chart-canvas {
  width: 100%;
  height: 100%;
  min-height: 700px;
}

/* Floating Legend Style */
.flow-chart-legend {
  position: absolute;
  left: 20px;
  bottom: 20px;
  background: rgba(30, 25, 20, 0.95);
  border: 1px solid rgba(211, 162, 106, 0.4);
  border-radius: 14px;
  padding: 14px;
  color: #ffffff;
  font-family: system-ui, sans-serif;
  font-size: 11px;
  z-index: 10;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(6px);
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 175px;
  pointer-events: auto;
}

.legend-title {
  font-weight: 700;
  font-size: 12px;
  border-bottom: 1px solid rgba(211, 162, 106, 0.3);
  padding-bottom: 6px;
  color: #d3a26a;
}

.legend-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.legend-group-title {
  color: rgba(255, 255, 255, 0.45);
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-line {
  width: 18px;
  height: 3px;
  border-radius: 1.5px;
  display: inline-block;
}

.line-spouse {
  background: #ff4d4d;
}

.line-child {
  background: #4d7cff;
  position: relative;
}
.line-child::after {
  content: '';
  position: absolute;
  right: 0;
  top: -2px;
  border-left: 4px solid #4d7cff;
  border-top: 3.5px solid transparent;
  border-bottom: 3.5px solid transparent;
}

.legend-pin {
  width: 10px;
  height: 10px;
  background: #4d7cff;
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg);
  display: inline-block;
  margin-left: 4px;
  margin-right: 4px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  border: 1px solid #ffffff;
}

.dot-millennial {
  background: #ff85a2;
}

.dot-modern {
  background: #ffbe5c;
}

.dot-classic {
  background: #5cb8ff;
}

.dot-deceased {
  background: #a0a0a0;
  border-color: #666666;
  background-image: linear-gradient(45deg, rgba(0,0,0,0.15) 25%, transparent 25%, transparent 50%, rgba(0,0,0,0.15) 50%, rgba(0,0,0,0.15) 75%, transparent 75%, transparent);
  background-size: 4px 4px;
}

.dot-active {
  background: #5cb8ff;
  border: 2px solid #c48b58;
  box-shadow: 0 0 4px #c48b58;
}
</style>
