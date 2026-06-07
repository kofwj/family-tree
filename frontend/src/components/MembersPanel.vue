<template>
  <div class="members-page">
    <section class="quality-board">
      <div class="quality-board__hero">
        <div>
          <p class="quality-board__eyebrow">宗亲资料质检台</p>
          <h3>成员录数据质量视图</h3>
          <p>优先把可补录成员、主线成员缺项和基础关系缺口快速筛出来，适合持续补档。</p>
        </div>
        <div class="quality-board__summary">
          <div class="summary-pill">
            <span>平均完整度</span>
            <strong>{{ averageCompleteness }}%</strong>
          </div>
          <div class="summary-pill summary-pill--warn" v-if="incompleteCount">
            <span>待补成员</span>
            <strong>{{ incompleteCount }}</strong>
          </div>
          <div class="summary-pill summary-pill--neutral">
            <span>当前结果</span>
            <strong>{{ filteredMembers.length }}</strong>
          </div>
        </div>
      </div>

      <div class="quality-board__grid">
        <button
          v-for="item in dashboardCards"
          :key="item.value"
          type="button"
          class="quality-card"
          :class="[
            `quality-card--${item.tone || 'default'}`,
            { 'quality-card--active': qualityFilter === item.value },
          ]"
          @click="toggleQualityFilter(item.value)"
        >
          <div class="quality-card__head">
            <span class="quality-card__label">{{ item.label }}</span>
            <strong class="quality-card__count">{{ qualityCounts[item.value] || 0 }}</strong>
          </div>
          <p class="quality-card__desc">{{ item.description }}</p>
        </button>
      </div>

      <div class="quality-board__toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="keyword"
            class="member-search"
            clearable
            placeholder="搜索姓名、配偶、父母、出生地、居住地"
          />
          <el-select v-model="genderFilter" class="toolbar-select" placeholder="性别" clearable>
            <el-option label="男" value="男" />
            <el-option label="女" value="女" />
          </el-select>
          <el-select v-model="generationFilter" class="toolbar-select" placeholder="世代" clearable>
            <el-option v-for="g in generations" :key="g" :label="`第${g}代`" :value="g" />
          </el-select>
          <el-select v-model="qualityFilter" class="toolbar-select quality-select" placeholder="数据质量视图">
            <el-option v-for="item in qualityOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select
            v-if="qualityFilter === 'lowCompleteness'"
            v-model="lowCompletenessThreshold"
            class="toolbar-select threshold-select"
            placeholder="完整度阈值"
          >
            <el-option label="低于 50%" :value="50" />
            <el-option label="低于 60%" :value="60" />
            <el-option label="低于 70%" :value="70" />
            <el-option label="低于 80%" :value="80" />
          </el-select>
        </div>

        <div class="toolbar-right">
          <el-tag v-if="activeQualityMeta" :type="activeQualityMeta.tagType || 'warning'">{{ activeQualityMeta.label }}</el-tag>
          <el-tag :type="averageCompleteness >= 80 ? 'success' : averageCompleteness >= 60 ? 'warning' : 'danger'">
            平均完整度 {{ averageCompleteness }}%
          </el-tag>
          <el-tag v-if="incompleteCount" type="warning">待补 {{ incompleteCount }} 人</el-tag>
          <el-tag type="info">共 {{ filteredMembers.length }} 人</el-tag>
          <el-button v-if="canConfigFields" size="small" plain @click="openFieldDialog">显示字段</el-button>
          <el-button size="small" plain @click="resetFilters">重置筛选</el-button>
          <el-radio-group v-model="mode" size="small">
            <el-radio-button label="table">表格</el-radio-button>
            <el-radio-button label="card">卡片</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </section>

    <el-table
      v-if="mode === 'table'"
      class="members-table"
      :data="filteredMembers"
      height="calc(100vh - 420px)"
      stripe
      border
      highlight-current-row
      :row-class-name="rowClassName"
      @row-click="open"
    >
      <el-table-column type="index" label="#" width="54" align="center" fixed="left" />
      <el-table-column label="完整度" width="124" align="center" fixed="left">
        <template #default="{ row }">
          <div class="completion-cell">
            <el-progress
              :percentage="memberCompleteness(row).score"
              :stroke-width="7"
              :show-text="false"
              :status="completionStatus(memberCompleteness(row).score)"
            />
            <span>{{ memberCompleteness(row).score }}%</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column
        v-for="col in displayedColumns"
        :key="col.key"
        :prop="col.key"
        :label="col.label"
        :width="col.width"
        :min-width="col.minWidth"
        :align="col.align || 'left'"
        :fixed="col.fixed"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <div v-if="col.key === 'name'" class="member-name-cell">
            <strong>{{ row.name || '未命名' }}</strong>
            <span>
              <el-tag v-if="row.generation" size="small" effect="plain">第{{ row.generation }}代</el-tag>
              <el-tag v-if="row.rankTitle" size="small" type="warning" effect="plain">{{ row.rankTitle }}</el-tag>
              <el-tag v-if="row.branch" size="small" type="success" effect="plain">{{ row.branch }}</el-tag>
              <el-tag v-if="row.isCoreMember" size="small" type="danger" effect="plain">主线</el-tag>
            </span>
          </div>
          <el-tag v-else-if="col.key === 'gender'" :type="row.gender === '女' ? 'danger' : row.gender === '男' ? 'primary' : 'info'" effect="plain">
            {{ row.gender || '未知' }}
          </el-tag>
          <span v-else-if="col.key === 'generation'">{{ row.generation ? `第${row.generation}代` : '—' }}</span>
          <span v-else-if="col.key === 'birthDate' || col.key === 'deathDate'">{{ formatDate(row[col.key]) }}</span>
          <el-tag v-else-if="col.key === 'isLiving'" :type="row.isLiving === false ? 'info' : 'success'" effect="plain">
            {{ row.isLiving === false ? '已故' : '健在' }}
          </el-tag>
          <el-tag v-else-if="col.key === 'isCoreMember' || col.key === 'isPublic'" :type="row[col.key] === false ? 'info' : 'success'" effect="plain">
            {{ row[col.key] === false ? '否' : '是' }}
          </el-tag>
          <span v-else-if="['fatherId', 'motherId', 'spouseIds'].includes(col.key)">{{ relationText(row, col.key) }}</span>
          <span v-else>{{ displayValue(row[col.key]) }}</span>
        </template>
      </el-table-column>

      <el-table-column v-if="canEdit || canDelete" label="操作" width="132" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canEdit && row.visibilityScope !== 'basic'" link type="primary" size="small" @click.stop="$emit('edit-member', row)">编辑</el-button>
          <el-button v-if="canDelete && row.visibilityScope !== 'basic'" link type="danger" size="small" @click.stop="$emit('delete-member', row)">删除</el-button>
          <el-tag v-if="row.visibilityScope === 'basic'" size="small" type="info" effect="plain">关系可见</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <div v-else class="member-cards enhanced-cards">
      <el-card v-for="m in filteredMembers" :key="m.id" class="member-card" @click="open(m)">
        <div class="card-head">
          <h4>👤 {{ m.name }}</h4>
          <el-tag size="small" :type="m.gender === '女' ? 'danger' : 'primary'" effect="plain">{{ m.gender || '未知' }}</el-tag>
        </div>
        <p>第{{ m.generation || '?' }}代 · {{ m.generationName || '字辈待补' }} · {{ m.rankTitle || '排行待补' }}</p>
        <p>{{ m.branch || '支系待补' }} · {{ m.occupation || m.positionTitle || '职业身份待补' }}</p>
        <p>{{ m.birthPlace || m.residence || m.ancestralOrigin || '籍贯待补充' }}</p>
        <div class="card-completion">
          <span>资料完整度 {{ memberCompleteness(m).score }}%</span>
          <el-progress
            :percentage="memberCompleteness(m).score"
            :stroke-width="6"
            :show-text="false"
            :status="completionStatus(memberCompleteness(m).score)"
          />
        </div>
        <div class="member-card__flags">
          <el-tag v-if="m.isCoreMember" size="small" type="danger" effect="plain">主线成员</el-tag>
          <el-tag v-if="isSupplementActionable(m)" size="small" type="warning" effect="plain">可补录</el-tag>
        </div>
        <div v-if="memberCompleteness(m).missing.length" class="missing-mini">
          <el-tag v-for="field in memberCompleteness(m).missing.slice(0, 4)" :key="field" size="small" type="warning" effect="plain">缺{{ field }}</el-tag>
        </div>
        <small>配偶：{{ relationText(m, 'spouseIds') || '暂无' }}</small>
      </el-card>
    </div>

    <el-dialog v-model="fieldDialogVisible" title="成员录显示字段" width="760px" class="member-field-dialog" destroy-on-close>
      <div class="field-dialog-head">
        <div>
          <strong>选择表格中要显示的字段</strong>
          <p>姓名固定显示；勾选后保存，会立即应用到成员录表格。</p>
        </div>
        <el-tag type="info">已选 {{ draftVisibleFields.length }} 项</el-tag>
      </div>

      <div class="field-dialog-actions">
        <el-button size="small" @click="selectCoreFields">常用字段</el-button>
        <el-button size="small" @click="selectArchiveFields">档案字段</el-button>
        <el-button size="small" @click="selectAllFields">全选</el-button>
        <el-button size="small" @click="resetFieldDraft">恢复当前</el-button>
      </div>

      <el-checkbox-group v-model="draftVisibleFields" class="field-group-list">
        <div v-for="group in fieldGroups" :key="group.title" class="field-group-card">
          <div class="field-group-title">
            <span>{{ group.title }}</span>
            <small>{{ group.fields.length }} 项</small>
          </div>
          <div class="field-group-checks">
            <el-checkbox
              v-for="field in group.fields"
              :key="field.key"
              :label="field.key"
              :disabled="field.key === 'name'"
            >
              {{ field.label }}
            </el-checkbox>
          </div>
        </div>
      </el-checkbox-group>

      <template #footer>
        <el-button @click="fieldDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveFieldDraft">保存显示字段</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  members: { type: Array, default: () => [] },
  visibleFields: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
  canConfigFields: { type: Boolean, default: false },
})

const emit = defineEmits(['open-member', 'edit-member', 'delete-member', 'update-visible-fields'])
const mode = ref('table')
const keyword = ref('')
const genderFilter = ref('')
const generationFilter = ref(null)
const qualityFilter = ref('all')
const lowCompletenessThreshold = ref(60)
const fieldDialogVisible = ref(false)
const draftVisibleFields = ref([])

const supplementFocusFields = [
  { key: 'birthDate', label: '出生日期' },
  { key: 'birthPlace', label: '出生地' },
  { key: 'residence', altKeys: ['currentResidence'], label: '现居住地' },
  { key: 'occupation', label: '职业' },
  { key: 'positionTitle', label: '职务/身份' },
  { key: 'source', label: '资料来源' },
  { key: 'biography', label: '传略' },
]

const qualityOptions = [
  { label: '全部成员', value: 'all', tagType: 'info' },
  { label: '仅看可补录成员', value: 'actionableSupplement', tagType: 'warning' },
  { label: '仅看核心成员缺项', value: 'coreMissing', tagType: 'danger' },
  { label: '仅看主线缺来源', value: 'coreMissingSource', tagType: 'danger' },
  { label: '仅看主线缺传略', value: 'coreMissingBiography', tagType: 'danger' },
  { label: '仅看主线低完整度', value: 'coreLowCompleteness', tagType: 'danger' },
  { label: '缺父亲', value: 'missingFather', tagType: 'warning' },
  { label: '缺母亲', value: 'missingMother', tagType: 'warning' },
  { label: '缺配偶', value: 'missingSpouse', tagType: 'info' },
  { label: '缺资料来源', value: 'missingSource', tagType: 'warning' },
  { label: '缺传略', value: 'missingBiography', tagType: 'warning' },
  { label: '完整度低', value: 'lowCompleteness', tagType: 'danger' },
]

const dashboardCards = [
  { label: '可补录成员', value: 'actionableSupplement', description: '优先补职业、来源、传略、出生地等可追字段', tone: 'gold' },
  { label: '主线成员缺项', value: 'coreMissing', description: '优先保证本族主线人物档案完整', tone: 'red' },
  { label: '主线缺来源', value: 'coreMissingSource', description: '主线人物先补证据链，降低后续校谱争议', tone: 'red' },
  { label: '主线缺传略', value: 'coreMissingBiography', description: '优先补人物经历，提升主线成员阅读价值', tone: 'brown' },
  { label: '主线低完整度', value: 'coreLowCompleteness', description: '聚焦主线骨架中的低完整度人物', tone: 'purple' },
  { label: '缺资料来源', value: 'missingSource', description: '缺证据链，后续校谱最容易卡住', tone: 'amber' },
  { label: '缺传略', value: 'missingBiography', description: '可优先补人生经历、家族贡献、迁徙信息', tone: 'brown' },
  { label: '缺父亲', value: 'missingFather', description: '先补直系父链，避免树结构断层', tone: 'slate' },
  { label: '缺母亲', value: 'missingMother', description: '补母系信息有助于后续人物档案完善', tone: 'slate' },
  { label: '缺配偶', value: 'missingSpouse', description: '适合婚配关系集中补录', tone: 'blue' },
  { label: '完整度低', value: 'lowCompleteness', description: '按阈值筛出低完整度成员集中整理', tone: 'purple' },
]

const completenessFields = [
  { key: 'name', label: '姓名', required: true },
  { key: 'gender', label: '性别', required: true },
  { key: 'generation', label: '世代', required: true },
  { key: 'generationName', label: '字辈' },
  { key: 'rankTitle', label: '排行' },
  { key: 'branch', label: '支系' },
  { key: 'birthDate', label: '出生日期' },
  { key: 'birthPlace', label: '出生地' },
  { key: 'ancestralOrigin', label: '祖籍' },
  { key: 'residence', altKeys: ['currentResidence'], label: '现居住地' },
  { key: 'fatherId', label: '父亲' },
  { key: 'motherId', label: '母亲' },
  { key: 'spouseIds', label: '配偶' },
  { key: 'source', label: '资料来源' },
  { key: 'biography', label: '传略' },
]

function fieldValue(member, field) {
  const keys = [field.key, ...(field.altKeys || [])]
  for (const key of keys) {
    const value = member?.[key]
    if (Array.isArray(value) && value.length) return value
    if (value !== null && value !== undefined && String(value).trim() !== '') return value
  }
  return ''
}

function hasValue(value) {
  if (Array.isArray(value)) return value.some(item => hasValue(item))
  return value !== null && value !== undefined && String(value).trim() !== ''
}

function hasRelation(member, key) {
  if (key === 'spouseIds') return Array.isArray(member?.spouseIds) && member.spouseIds.length > 0
  return hasValue(member?.[key])
}

function memberCompleteness(member) {
  const missing = completenessFields.filter(field => !fieldValue(member, field)).map(field => field.label)
  const filled = completenessFields.length - missing.length
  return {
    score: Math.round((filled / completenessFields.length) * 100),
    missing,
  }
}

function completionStatus(score) {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'exception'
}

function isSupplementActionable(member) {
  return supplementFocusFields.some(field => !hasValue(fieldValue(member, field)))
}

function isCoreMissing(member) {
  return Boolean(member?.isCoreMember) && memberCompleteness(member).score < 100
}

function isCoreMissingSource(member) {
  return Boolean(member?.isCoreMember) && !hasValue(fieldValue(member, { key: 'source' }))
}

function isCoreMissingBiography(member) {
  return Boolean(member?.isCoreMember) && !hasValue(fieldValue(member, { key: 'biography' }))
}

function isCoreLowCompleteness(member) {
  return Boolean(member?.isCoreMember) && memberCompleteness(member).score < Number(lowCompletenessThreshold.value || 60)
}

const defaultVisibleFields = [
  'name', 'gender', 'generation', 'generationName', 'rankTitle',
  'branch', 'birthDate', 'birthPlace', 'residence', 'spouseIds', 'fatherId', 'motherId'
]

const columnMap = {
  name: { key: 'name', label: '姓名', minWidth: 170, fixed: 'left' },
  formerName: { key: 'formerName', label: '曾用名', minWidth: 110 },
  courtesyName: { key: 'courtesyName', label: '字', width: 92, align: 'center' },
  artName: { key: 'artName', label: '号', width: 92, align: 'center' },
  childhoodName: { key: 'childhoodName', label: '乳名', width: 96, align: 'center' },
  gender: { key: 'gender', label: '性别', width: 76, align: 'center' },
  generation: { key: 'generation', label: '世代', width: 88, align: 'center' },
  generationName: { key: 'generationName', label: '字辈', width: 92, align: 'center' },
  rankNo: { key: 'rankNo', label: '排行序号', width: 96, align: 'center' },
  rankTitle: { key: 'rankTitle', label: '排行', width: 96, align: 'center' },
  branch: { key: 'branch', label: '支系/房支', minWidth: 120 },
  isCoreMember: { key: 'isCoreMember', label: '本族主线', width: 96, align: 'center' },
  birthDate: { key: 'birthDate', label: '出生日期', minWidth: 116 },
  deathDate: { key: 'deathDate', label: '去世日期', minWidth: 116 },
  birthPlace: { key: 'birthPlace', label: '出生地', minWidth: 150 },
  deathPlace: { key: 'deathPlace', label: '去世地', minWidth: 150 },
  residence: { key: 'residence', label: '现居住地', minWidth: 150 },
  ancestralOrigin: { key: 'ancestralOrigin', label: '祖籍/籍贯', minWidth: 140 },
  burialPlace: { key: 'burialPlace', label: '安葬地/墓址', minWidth: 150 },
  isLiving: { key: 'isLiving', label: '健在', width: 80, align: 'center' },
  spouseIds: { key: 'spouseIds', label: '配偶', minWidth: 120 },
  fatherId: { key: 'fatherId', label: '父亲', minWidth: 100 },
  motherId: { key: 'motherId', label: '母亲', minWidth: 100 },
  childrenNote: { key: 'childrenNote', label: '子女备注', minWidth: 150 },
  marriageNote: { key: 'marriageNote', label: '婚配说明', minWidth: 150 },
  education: { key: 'education', label: '学历', minWidth: 100 },
  occupation: { key: 'occupation', label: '职业', minWidth: 120 },
  positionTitle: { key: 'positionTitle', label: '职务/身份', minWidth: 130 },
  biography: { key: 'biography', label: '传略', minWidth: 180 },
  source: { key: 'source', label: '资料来源', minWidth: 140 },
  isPublic: { key: 'isPublic', label: '公开', width: 80, align: 'center' },
}

const fieldGroups = [
  {
    title: '基础身份',
    fields: [
      columnMap.name, columnMap.formerName, columnMap.courtesyName, columnMap.artName,
      columnMap.childhoodName, columnMap.gender,
    ],
  },
  {
    title: '宗谱信息',
    fields: [
      columnMap.generation, columnMap.generationName, columnMap.rankNo, columnMap.rankTitle,
      columnMap.branch, columnMap.isCoreMember,
    ],
  },
  {
    title: '生卒地点',
    fields: [
      columnMap.birthDate, columnMap.deathDate, columnMap.birthPlace, columnMap.deathPlace,
      columnMap.residence, columnMap.ancestralOrigin, columnMap.burialPlace, columnMap.isLiving,
    ],
  },
  {
    title: '亲属关系',
    fields: [
      columnMap.spouseIds, columnMap.fatherId, columnMap.motherId,
      columnMap.childrenNote, columnMap.marriageNote,
    ],
  },
  {
    title: '人物档案',
    fields: [
      columnMap.education, columnMap.occupation, columnMap.positionTitle,
      columnMap.biography, columnMap.source, columnMap.isPublic,
    ],
  },
]

const allFieldKeys = fieldGroups.flatMap(group => group.fields.map(field => field.key))

function normalizeFields(fields) {
  const source = fields?.length ? fields : defaultVisibleFields
  const fieldAliasMap = {
    spouse: 'spouseIds',
    spouseName: 'spouseIds',
    fatherName: 'fatherId',
    motherName: 'motherId',
  }
  const normalized = source
    .map(f => fieldAliasMap[f] || f)
    .filter(f => columnMap[f])
  const unique = Array.from(new Set(normalized))
  return unique.includes('name') ? unique : ['name', ...unique]
}

function resetFieldDraft() {
  draftVisibleFields.value = normalizeFields(props.visibleFields)
}

function openFieldDialog() {
  resetFieldDraft()
  fieldDialogVisible.value = true
}

function selectCoreFields() {
  draftVisibleFields.value = normalizeFields(defaultVisibleFields)
}

function selectArchiveFields() {
  draftVisibleFields.value = normalizeFields([
    'name', 'gender', 'generation', 'generationName', 'rankTitle', 'branch',
    'birthDate', 'deathDate', 'birthPlace', 'residence', 'ancestralOrigin',
    'spouseIds', 'fatherId', 'motherId', 'occupation', 'source', 'biography', 'isCoreMember'
  ])
}

function selectAllFields() {
  draftVisibleFields.value = normalizeFields(allFieldKeys)
}

function saveFieldDraft() {
  const fields = normalizeFields(draftVisibleFields.value)
  draftVisibleFields.value = fields
  emit('update-visible-fields', fields)
  fieldDialogVisible.value = false
}

function resetFilters() {
  keyword.value = ''
  genderFilter.value = ''
  generationFilter.value = null
  qualityFilter.value = 'all'
  lowCompletenessThreshold.value = 60
}

const generations = computed(() => Array.from(new Set((props.members || []).map(m => m.generation).filter(Boolean))).sort((a, b) => a - b))

function matchesQualityFilter(member, filter) {
  switch (filter) {
    case 'actionableSupplement':
      return isSupplementActionable(member)
    case 'coreMissing':
      return isCoreMissing(member)
    case 'coreMissingSource':
      return isCoreMissingSource(member)
    case 'coreMissingBiography':
      return isCoreMissingBiography(member)
    case 'coreLowCompleteness':
      return isCoreLowCompleteness(member)
    case 'missingFather':
      return !hasRelation(member, 'fatherId')
    case 'missingMother':
      return !hasRelation(member, 'motherId')
    case 'missingSpouse':
      return !hasRelation(member, 'spouseIds')
    case 'missingSource':
      return !hasValue(fieldValue(member, { key: 'source' }))
    case 'missingBiography':
      return !hasValue(fieldValue(member, { key: 'biography' }))
    case 'lowCompleteness':
      return memberCompleteness(member).score < Number(lowCompletenessThreshold.value || 60)
    default:
      return true
  }
}

const qualityCounts = computed(() => {
  const result = {}
  for (const item of qualityOptions) {
    if (item.value === 'all') continue
    result[item.value] = (props.members || []).filter(member => matchesQualityFilter(member, item.value)).length
  }
  return result
})

const filteredMembers = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return (props.members || []).filter(m => {
    if (genderFilter.value && m.gender !== genderFilter.value) return false
    if (generationFilter.value && Number(m.generation) !== Number(generationFilter.value)) return false
    if (!matchesQualityFilter(m, qualityFilter.value)) return false
    if (!q) return true
    const haystack = [
      m.name, m.formerName, m.courtesyName, m.artName, m.childhoodName,
      m.gender, m.generation, m.generationName, m.rankTitle, m.branch,
      m.birthDate, m.deathDate, m.birthPlace, m.deathPlace, m.residence, m.ancestralOrigin, m.burialPlace,
      relationText(m, 'spouseIds'), relationText(m, 'fatherId'), relationText(m, 'motherId'), m.childrenNote, m.marriageNote,
      m.education, m.occupation, m.positionTitle, m.biography, m.source,
    ].filter(Boolean).join(' ').toLowerCase()
    return haystack.includes(q)
  })
})

const averageCompleteness = computed(() => {
  if (!filteredMembers.value.length) return 0
  const total = filteredMembers.value.reduce((sum, member) => sum + memberCompleteness(member).score, 0)
  return Math.round(total / filteredMembers.value.length)
})

const incompleteCount = computed(() => filteredMembers.value.filter(member => memberCompleteness(member).score < 80).length)
const activeQualityMeta = computed(() => qualityOptions.find(item => item.value === qualityFilter.value && item.value !== 'all') || null)
const activeFields = computed(() => normalizeFields(props.visibleFields))
const displayedColumns = computed(() => activeFields.value.map(f => columnMap[f]).filter(Boolean))

function toggleQualityFilter(value) {
  qualityFilter.value = qualityFilter.value === value ? 'all' : value
}

function findMemberNameById(id) {
  const target = Number(id)
  if (!Number.isFinite(target)) return ''
  return (props.members || []).find(m => Number(m.id) === target)?.name || ''
}

function relationText(member, key) {
  if (key === 'fatherId') return findMemberNameById(member?.fatherId) || '—'
  if (key === 'motherId') return findMemberNameById(member?.motherId) || '—'
  if (key === 'spouseIds') {
    const names = (Array.isArray(member?.spouseIds) ? member.spouseIds : []).map(findMemberNameById).filter(Boolean)
    return names.length ? names.join('、') : '—'
  }
  return ''
}

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '—' : value
}

function formatDate(value) {
  if (!value) return '—'
  return String(value).slice(0, 10)
}

function rowClassName({ row }) {
  if (qualityFilter.value === 'coreMissing' && isCoreMissing(row)) return 'member-row-core-missing'
  if (qualityFilter.value === 'actionableSupplement' && isSupplementActionable(row)) return 'member-row-actionable'
  return row.gender === '女' ? 'member-row-female' : row.gender === '男' ? 'member-row-male' : ''
}

function open(member) {
  emit('open-member', member)
}
</script>

<style scoped>
.members-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.quality-board {
  border-radius: 20px;
  padding: 18px;
  background: linear-gradient(180deg, rgba(250, 246, 238, 0.98), rgba(245, 237, 225, 0.94));
  border: 1px solid rgba(133, 94, 66, 0.12);
  box-shadow: 0 16px 40px rgba(84, 55, 27, 0.08);
}

.quality-board__hero {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.quality-board__eyebrow {
  margin: 0 0 6px;
  color: #9c6a3a;
  font-size: 12px;
  letter-spacing: 0.12em;
}

.quality-board__hero h3 {
  margin: 0 0 8px;
  font-size: 24px;
  color: #5f4228;
}

.quality-board__hero p {
  margin: 0;
  color: #7d644b;
  line-height: 1.6;
}

.quality-board__summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.summary-pill {
  min-width: 108px;
  padding: 10px 14px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(190, 162, 127, 0.28);
}

.summary-pill span {
  display: block;
  font-size: 12px;
  color: #8b7154;
  margin-bottom: 4px;
}

.summary-pill strong {
  font-size: 22px;
  color: #6a4726;
}

.summary-pill--warn {
  background: rgba(255, 247, 230, 0.92);
}

.summary-pill--neutral {
  background: rgba(244, 247, 252, 0.92);
}

.quality-board__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.quality-card {
  text-align: left;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(145, 109, 67, 0.12);
  background: rgba(255, 255, 255, 0.9);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.quality-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 24px rgba(97, 62, 28, 0.08);
}

.quality-card--active {
  border-color: rgba(166, 104, 37, 0.55);
  box-shadow: 0 16px 28px rgba(154, 101, 43, 0.16);
}

.quality-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.quality-card__label {
  font-size: 15px;
  font-weight: 600;
  color: #5b4027;
}

.quality-card__count {
  font-size: 28px;
  line-height: 1;
  color: #9a5d24;
}

.quality-card__desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #7c6854;
}

.quality-card--gold .quality-card__count { color: #b7771d; }
.quality-card--red .quality-card__count { color: #c45656; }
.quality-card--amber .quality-card__count { color: #d48806; }
.quality-card--brown .quality-card__count { color: #8c6239; }
.quality-card--slate .quality-card__count { color: #566b8f; }
.quality-card--blue .quality-card__count { color: #2f6ec8; }
.quality-card--purple .quality-card__count { color: #7b61c8; }

.quality-board__toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.member-search {
  width: 260px;
}

.toolbar-select {
  min-width: 120px;
}

.quality-select {
  min-width: 170px;
}

.threshold-select {
  min-width: 120px;
}

.member-card__flags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 10px 0 8px;
}

.completion-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.member-name-cell {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.member-name-cell span {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.missing-mini {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin: 10px 0;
}

:deep(.member-row-core-missing) {
  --el-table-tr-bg-color: rgba(255, 238, 238, 0.85);
}

:deep(.member-row-actionable) {
  --el-table-tr-bg-color: rgba(255, 248, 233, 0.9);
}

@media (max-width: 980px) {
  .quality-board__hero {
    flex-direction: column;
  }

  .quality-board__summary {
    justify-content: flex-start;
  }
}
</style>
