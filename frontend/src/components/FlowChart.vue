<template>
  <div class="hierarchical-tree" ref="containerRef">
    <svg ref="svgRef" class="ht-svg" :viewBox="`0 0 ${svgWidth} ${svgHeight}`"
      :style="{ transform: `scale(${zoom})`, transformOrigin: 'top left' }">
      <defs>
        <linearGradient id="htGradMale" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#1e3a60"/><stop offset="100%" stop-color="#152a48"/>
        </linearGradient>
        <linearGradient id="htGradFemale" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#4a2040"/><stop offset="100%" stop-color="#3a1830"/>
        </linearGradient>
        <filter id="htShadow"><feDropShadow dx="0" dy="1" stdDeviation="3" flood-opacity=".35"/></filter>
      </defs>
      <g :transform="`translate(${offsetX}, ${offsetY})`">
        <path v-for="line in lines" :key="line.key" :d="line.d" :class="['ht-line', line.type]"/>
        <g v-for="node in nodes" :key="node.id" class="ht-node"
          :class="{ active: Number(node.id) === Number(activeMemberId), focused: Number(node.id) === Number(focusedId) }"
          :transform="`translate(${node.x}, ${node.y})`" filter="url(#htShadow)"
          @click="handleNodeClick(node)"
          @mouseenter="handleMouseEnter($event, node)"
          @mousemove="handleMouseMove($event)"
          @mouseleave="handleMouseLeave">
          <rect class="ht-node-bg" :width="NODE_W" :height="NODE_H" rx="6" ry="6"
            :fill="node.gender === '女' ? 'url(#htGradFemale)' : 'url(#htGradMale)'"
            :stroke="node.gender === '女' ? '#c06080' : '#3a7ac0'"
            :stroke-width="Number(node.id) === Number(activeMemberId) ? 2.5 : 1.5"/>
          <circle :cx="22" :cy="NODE_H / 2" r="16"
            :fill="node.gender === '女' ? '#5a2a48' : '#2a4a70'"
            :stroke="node.gender === '女' ? '#d07090' : '#4a8ad0'" stroke-width="1"/>
          <text :x="22" :y="NODE_H / 2 + 5" text-anchor="middle"
            :fill="node.gender === '女' ? '#e8a0b8' : '#b0c8e0'" font-size="13">{{ node.avatar }}</text>
          <text class="ht-node-name" :x="44" :y="20">{{ node.name }}</text>
          <text class="ht-node-relation" :x="44" :y="35">{{ node.relation }}</text>
          <text class="ht-node-dates" :x="44" :y="48">{{ node.dateText }}</text>
        </g>
      </g>
    </svg>
    <div class="ht-tooltip" :class="{ show: tooltipVisible }" :style="tooltipStyle">
      <div class="ht-tt-name">{{ tooltipData.name }}</div>
      <div class="ht-tt-row" v-if="tooltipData.gender">性别: {{ tooltipData.gender }}</div>
      <div class="ht-tt-row" v-if="tooltipData.relation">{{ tooltipData.relation }}</div>
      <div class="ht-tt-row" v-if="tooltipData.dateText">{{ tooltipData.dateText }}</div>
      <div class="ht-tt-row" v-if="tooltipData.spouseName">配偶: {{ tooltipData.spouseName }}</div>
      <div class="ht-tt-row" v-if="tooltipData.childCount">子女: {{ tooltipData.childCount }}人</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import dagre from 'dagre'

const props = defineProps({
  members: { type: Array, default: () => [] },
  activeMemberId: { type: [Number, String], default: null },
  searchKeyword: { type: String, default: '' },
  generationLimit: { type: [String, Number], default: 'all' },
})
const emit = defineEmits(['node-click'])

const NODE_W = 152
const NODE_H = 56
const COUPLE_GAP = 10
const containerRef = ref(null)
const svgRef = ref(null)
const zoom = ref(1)
const offsetX = ref(30)
const offsetY = ref(30)
const focusedId = ref(null)
const svgWidth = ref(1400)
const svgHeight = ref(900)

// Tooltip state
const tooltipVisible = ref(false)
const tooltipStyle = ref({})
const tooltipData = ref({})

// Build member lookup
const memberById = computed(() => {
  const map = new Map()
  for (const m of props.members) map.set(Number(m.id), m)
  return map
})

// Get children of a member
function getChildren(parentId) {
  return props.members.filter(m =>
    Number(m.fatherId) === parentId || Number(m.motherId) === parentId
  )
}

// Get spouse IDs for a member
function getSpouseIds(m) {
  if (!m) return []
  if (Array.isArray(m.spouseIds)) return m.spouseIds.map(Number)
  if (typeof m.spouseIds === 'string') {
    try { return JSON.parse(m.spouseIds).map(Number) } catch { return [] }
  }
  return []
}

// Find root member (highest generation, no parents)
function findRoot() {
  const candidates = props.members
    .filter(m => !m.fatherId && !m.motherId)
    .sort((a, b) => (a.generation ?? 999) - (b.generation ?? 999))
  return candidates[0] || props.members[0]
}

// Format date display
function formatDates(m) {
  const birth = m.birthDate || m.birthDateText || ''
  const death = m.deathDate || m.deathDateText || ''
  if (!birth && !death) return ''
  if (death) return `${birth}–${death}`
  return `${birth}–`
}

// Get relation label
function getRelation(m) {
  if (m.generationName) return m.generationName
  if (m.generation != null) return `第${m.generation}代`
  return ''
}

// Core layout computation using dagre
const layoutResult = computed(() => {
  if (!props.members || props.members.length === 0) return { nodes: [], lines: [] }

  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', ranksep: 90, nodesep: 20, edgesep: 10 })
  g.setDefaultEdgeLabel(() => ({}))

  const root = findRoot()
  if (!root) return { nodes: [], lines: [] }

  // BFS to collect visible members (respecting generation limit)
  const limit = props.generationLimit === 'all' ? Infinity : Number(props.generationLimit)
  const rootGen = root.generation ?? 1
  const visibleIds = new Set()
  const queue = [root]
  visibleIds.add(Number(root.id))

  while (queue.length > 0) {
    const curr = queue.shift()
    const currGen = (curr.generation ?? rootGen) - rootGen
    // Add spouses
    for (const spId of getSpouseIds(curr)) {
      visibleIds.add(spId)
    }
    if (currGen >= limit) continue
    // Add children
    for (const child of getChildren(Number(curr.id))) {
      if (!visibleIds.has(Number(child.id))) {
        visibleIds.add(Number(child.id))
        queue.push(child)
      }
    }
  }

  // Spouse grouping: group members into couples for side-by-side placement
  const spouseGroupOf = new Map() // memberId -> groupKey
  const spouseGroups = new Map()  // groupKey -> [member, spouse?]
  const usedInGroup = new Set()

  for (const m of props.members) {
    if (!visibleIds.has(Number(m.id))) continue
    if (usedInGroup.has(Number(m.id))) continue

    const spouseIdsList = getSpouseIds(m)
    const spouseInVisible = spouseIdsList.find(spId => visibleIds.has(spId) && !usedInGroup.has(spId))
    const groupKey = `grp-${m.id}`

    if (spouseInVisible) {
      const sp = memberById.value.get(spouseInVisible)
      if (sp) {
        // Male first in group
        const pair = m.gender === '男' ? [m, sp] : [sp, m]
        spouseGroups.set(groupKey, pair)
        spouseGroupOf.set(Number(pair[0].id), groupKey)
        spouseGroupOf.set(Number(pair[1].id), groupKey)
        usedInGroup.add(Number(pair[0].id))
        usedInGroup.add(Number(pair[1].id))
      } else {
        spouseGroups.set(groupKey, [m])
        spouseGroupOf.set(Number(m.id), groupKey)
        usedInGroup.add(Number(m.id))
      }
    } else {
      spouseGroups.set(groupKey, [m])
      spouseGroupOf.set(Number(m.id), groupKey)
      usedInGroup.add(Number(m.id))
    }
  }

  // Add nodes to dagre graph (one node per spouse group)
  for (const [key, group] of spouseGroups) {
    const w = group.length === 2 ? NODE_W * 2 + COUPLE_GAP : NODE_W
    g.setNode(key, { width: w, height: NODE_H })
  }

  // Add edges: parent group -> child group
  const edgeSet = new Set()
  for (const m of props.members) {
    if (!visibleIds.has(Number(m.id))) continue
    const childGroupKey = spouseGroupOf.get(Number(m.id))
    if (!childGroupKey) continue

    for (const parentId of [m.fatherId, m.motherId]) {
      if (!parentId) continue
      const parentGroupKey = spouseGroupOf.get(Number(parentId))
      if (!parentGroupKey || parentGroupKey === childGroupKey) continue
      const edgeKey = `${parentGroupKey}->${childGroupKey}`
      if (!edgeSet.has(edgeKey)) {
        edgeSet.add(edgeKey)
        g.setEdge(parentGroupKey, childGroupKey)
      }
    }
  }

  // Run dagre layout
  dagre.layout(g)

  // Extract node positions and build output
  const resultNodes = []
  const resultLines = []

  for (const [key, group] of spouseGroups) {
    const dagreNode = g.node(key)
    if (!dagreNode) continue

    const baseX = dagreNode.x - dagreNode.width / 2
    const baseY = dagreNode.y - NODE_H / 2

    for (let i = 0; i < group.length; i++) {
      const m = group[i]
      const nodeX = baseX + i * (NODE_W + COUPLE_GAP)
      resultNodes.push({
        id: Number(m.id),
        name: m.name || '未命名',
        gender: m.gender || '未知',
        avatar: m.gender === '女' ? '♀' : '♂',
        relation: getRelation(m),
        dateText: formatDates(m),
        x: nodeX,
        y: baseY,
        member: m,
      })
    }

    // Spouse connector (dashed line between couple)
    if (group.length === 2) {
      const x1 = baseX + NODE_W
      const x2 = baseX + NODE_W + COUPLE_GAP
      const cy = baseY + NODE_H / 2
      resultLines.push({
        key: `spouse-${group[0].id}-${group[1].id}`,
        d: `M${x1},${cy} L${x2},${cy}`,
        type: 'spouse',
      })
    }
  }

  // Parent-child lines (orthogonal)
  for (const edgeKey of edgeSet) {
    const [parentKey, childKey] = edgeKey.split('->')
    const pNode = g.node(parentKey)
    const cNode = g.node(childKey)
    if (!pNode || !cNode) continue

    const px = pNode.x
    const py = pNode.y + NODE_H / 2
    const cx = cNode.x
    const cy = cNode.y - NODE_H / 2
    const midY = (py + cy) / 2

    resultLines.push({
      key: edgeKey,
      d: `M${px},${py} L${px},${midY} L${cx},${midY} L${cx},${cy}`,
      type: 'child',
    })
  }

  // Compute SVG dimensions
  let maxX = 0, maxY = 0
  for (const n of resultNodes) {
    if (n.x + NODE_W > maxX) maxX = n.x + NODE_W
    if (n.y + NODE_H > maxY) maxY = n.y + NODE_H
  }
  svgWidth.value = Math.max(maxX + 80, 1200)
  svgHeight.value = Math.max(maxY + 80, 600)

  return { nodes: resultNodes, lines: resultLines }
})

// Computed accessors
const nodes = computed(() => {
  const result = layoutResult.value.nodes
  const kw = props.searchKeyword?.toLowerCase() || ''
  if (!kw) return result
  return result.map(n => ({ ...n, dimmed: !n.name.toLowerCase().includes(kw) }))
})
const lines = computed(() => layoutResult.value.lines)

// Interactions
function handleNodeClick(node) {
  focusedId.value = Number(node.id)
  emit('node-click', Number(node.id))
}

function handleMouseEnter(e, node) {
  const m = node.member
  const spouseIds = getSpouseIds(m)
  const spouseNames = spouseIds.map(id => memberById.value.get(id)?.name).filter(Boolean)
  const children = getChildren(Number(m.id))
  tooltipData.value = {
    name: node.name,
    gender: node.gender,
    relation: node.relation,
    dateText: node.dateText,
    spouseName: spouseNames.join(', ') || '',
    childCount: children.length || 0,
  }
  tooltipVisible.value = true
  updateTooltipPos(e)
}

function handleMouseMove(e) { updateTooltipPos(e) }
function handleMouseLeave() { tooltipVisible.value = false }
function updateTooltipPos(e) {
  tooltipStyle.value = { left: (e.clientX + 14) + 'px', top: (e.clientY + 14) + 'px' }
}

// Zoom control (exposed for parent)
function zoomIn() { zoom.value = Math.min(zoom.value + 0.15, 2.5) }
function zoomOut() { zoom.value = Math.max(zoom.value - 0.15, 0.3) }
function zoomReset() { zoom.value = 1 }

defineExpose({ zoomIn, zoomOut, zoomReset })
</script>

<style scoped>
.hierarchical-tree {
  width: 100%; height: 100%; position: relative; overflow: auto;
  background: radial-gradient(ellipse at 50% 40%, #132433 0%, #0d1a26 70%);
}
.ht-svg { display: block; min-width: 100%; min-height: 100%; }
.ht-line { fill: none; stroke-width: 1.5; }
.ht-line.child { stroke: #2a4a6a; }
.ht-line.spouse { stroke: #4a6080; stroke-dasharray: 4 3; }
.ht-node { cursor: pointer; transition: filter .15s; }
.ht-node:hover { filter: brightness(1.2); }
.ht-node.active .ht-node-bg { stroke-width: 3 !important; }
.ht-node.focused .ht-node-bg { stroke-width: 2.5 !important; filter: drop-shadow(0 0 6px rgba(74,154,255,.5)); }
.ht-node-name { fill: #e0e8f0; font-size: 13px; font-weight: 600; }
.ht-node-relation { fill: #8aacc8; font-size: 11px; }
.ht-node-dates { fill: #6a8aaa; font-size: 10px; }
.ht-tooltip {
  position: fixed; background: #1a2c3a; border: 1px solid #2a4a6a;
  border-radius: 6px; padding: 10px 14px; font-size: 13px;
  pointer-events: none; opacity: 0; transition: opacity .15s; z-index: 200;
  min-width: 140px; color: #c8d6e5;
}
.ht-tooltip.show { opacity: 1; }
.ht-tt-name { font-weight: 600; margin-bottom: 4px; color: #e0e8f0; }
.ht-tt-row { margin-bottom: 2px; font-size: 12px; color: #8aacc8; }
</style>
