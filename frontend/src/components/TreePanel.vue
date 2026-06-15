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
          <el-button size="small" @click="resetSunburstZoom">返回始祖</el-button>
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

const chartRef = ref(null)
let chartInstance = null

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
      setLocalFocus(params.data.id)
      emit('node-click', params.data.id)
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

function getProcessedSunburstData() {
  const roots = [...(props.tree || [])].sort(sortByGenealogy)
  const maxDepth = generationLimit.value === 'all' ? Infinity : Number(generationLimit.value)
  
  const rootsMinGen = roots.length ? Math.min(...roots.map(root => {
    const gen = root?.generation ?? root?.generationNo;
    return gen !== null && gen !== undefined ? Number(gen) : 1;
  })) : 1
  const branchGen = rootsMinGen <= 1 ? 2 : rootsMinGen + 1
  
  const palette = branchPalette.value
  const majorBranchIndexMap = new Map()
  const familySurname = getFamilySurname(props.familyName)
  const familyBaseHue = getBaseHueForSurname(familySurname)
  
  function getBranchColor(node, branchNode, rootIndex, gen) {
    if (!branchNode) {
      return { H: familyBaseHue, S: 16, L: 60 }
    }
    const key = nodeKey(branchNode)
    if (!majorBranchIndexMap.has(key)) {
      majorBranchIndexMap.set(key, majorBranchIndexMap.size)
    }
    const index = majorBranchIndexMap.get(key)
    const hslStr = palette[index % palette.length]
    const match = hslStr.match(/hsl\((\d+),\s*(\d+)%,\s*(\d+)%\)/)
    if (match) {
      return {
        H: Number(match[1]),
        S: Number(match[2]),
        L: Number(match[3])
      }
    }
    return { H: familyBaseHue, S: 80, L: 45 }
  }
  
  function convertNode(node, depth, parentBranchNode, rootIndex) {
    const id = nodeKey(node)
    const gen = node.generation ?? depth
    
    let currentBranchNode = parentBranchNode
    if (gen === branchGen) {
      currentBranchNode = node
    }
    
    const branchColorInfo = getBranchColor(node, currentBranchNode, rootIndex, gen)
    const depthDiff = Math.max(0, gen - rootsMinGen)
    const hue = branchColorInfo.H
    const sat = Math.max(30, branchColorInfo.S - depthDiff * 7)
    const light = Math.min(85, branchColorInfo.L + depthDiff * 6)
    const color = `hsl(${hue}, ${sat}%, ${light}%)`
    
    const children = []
    if (depth < maxDepth && node.children && node.children.length) {
      const sortedChildren = [...node.children].sort(sortByGenealogy)
      for (const child of sortedChildren) {
        children.push(convertNode(child, depth + 1, currentBranchNode, rootIndex))
      }
    }
    
    const spouseNames = (node.spouses || []).map(s => s.name).filter(Boolean).join('、') || node.spouse || ''
    const displayName = spouseNames ? `${node.name}\n(配:${spouseNames.split('、')[0]})` : node.name
    
    return {
      id: id,
      name: displayName,
      value: 1,
      children: children.length ? children : undefined,
      itemStyle: {
        color: color,
        borderColor: '#ffffff',
        borderWidth: 1
      },
      label: {
        show: true
      },
      rawMember: node
    }
  }
  
  const convertedRoots = roots.map((root, rootIndex) => 
    convertNode(root, 1, null, rootIndex)
  )
  
  const keyword = normalizeText(searchKeyword.value).toLowerCase()
  const isSearchActive = !!keyword
  
  const finalRoots = []
  for (const root of convertedRoots) {
    const filtered = filterSunburstNode(root, isSearchActive, keyword)
    finalRoots.push(filtered.node)
  }
  
  return finalRoots
}

function renderChart() {
  if (!chartInstance) return
  const data = getProcessedSunburstData()
  
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
                点击扇区即可打开个人档案
              </div>
            </div>
          </div>
        `
      }
    },
    series: {
      type: 'sunburst',
      data: data,
      radius: [0, '95%'],
      sort: null,
      emphasis: {
        focus: 'ancestor'
      },
      levels: [
        {},
        {
          r0: '0%',
          r: '22%',
          label: {
            rotate: 'tangential',
            fontSize: 12,
            color: '#ffffff',
            textBorderColor: 'rgba(0,0,0,0.6)',
            textBorderWidth: 2
          }
        },
        {
          r0: '22%',
          r: '45%',
          label: {
            rotate: 'tangential',
            fontSize: 11,
            color: '#ffffff',
            textBorderColor: 'rgba(0,0,0,0.6)',
            textBorderWidth: 2
          }
        },
        {
          r0: '45%',
          r: '70%',
          label: {
            rotate: 'tangential',
            fontSize: 10,
            color: '#ffffff',
            textBorderColor: 'rgba(0,0,0,0.6)',
            textBorderWidth: 2
          }
        },
        {
          r0: '70%',
          r: '92%',
          label: {
            rotate: 'tangential',
            fontSize: 9,
            color: '#ffffff',
            textBorderColor: 'rgba(0,0,0,0.6)',
            textBorderWidth: 2
          },
          itemStyle: {
            borderWidth: 1.5
          }
        }
      ],
      nodeClick: 'zoom'
    }
  }
  chartInstance.setOption(option)
}

function resetSunburstZoom() {
  if (chartInstance) {
    chartInstance.dispatchAction({
      type: 'sunburstRootToNode',
      nodeId: null
    })
  }
}

function resetSunburstView() {
  searchKeyword.value = ''
  generationLimit.value = '5'
  resetSunburstZoom()
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

watch(() => props.tree, () => {
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
  if (!id || displayMode.value !== 'flow' || !chartInstance) return
  chartInstance.dispatchAction({
    type: 'sunburstRootToNode',
    nodeId: String(id)
  })
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
</style>
