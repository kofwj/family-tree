<template>
  <el-drawer
    v-model="visibleModel"
    size="620px"
    class="member-archive-drawer"
    :title="member ? `${member.name} · 成员档案` : '成员档案'"
  >
    <div v-if="member" class="archive-detail">
      <section class="archive-hero">
        <div class="archive-avatar archive-avatar--photo" v-if="member.photoUrl && authenticatedPhotoUrl">
          <img :src="authenticatedPhotoUrl" :alt="`${member.name || '成员'}照片`" />
        </div>
        <div v-else class="archive-avatar" :class="member.gender === '女' ? 'female' : 'male'">
          {{ initial }}
        </div>
        <div class="archive-identity">
          <div class="archive-kicker">PERSONAL ARCHIVE · 第{{ display(member.generation, '?') }}代</div>
          <h2>{{ member.name || '未命名成员' }}</h2>
          <div class="archive-aliases">
            <el-tag v-if="member.gender" size="small" :type="member.gender === '女' ? 'danger' : 'primary'" effect="plain">{{ member.gender }}</el-tag>
            <el-tag v-if="member.generationName" size="small" effect="plain">{{ member.generationName }}字辈</el-tag>
            <el-tag v-if="member.rankTitle" size="small" type="warning" effect="plain">{{ member.rankTitle }}</el-tag>
            <el-tag v-if="member.branch" size="small" type="success" effect="plain">{{ member.branch }}</el-tag>
            <el-tag v-if="member.isCoreMember === false" size="small" type="info" effect="plain">旁系/姻亲</el-tag>
            <el-tag v-if="isBasicVisible" size="small" type="info" effect="dark">关系基础可见</el-tag>
          </div>
          <p>{{ identityLine }}</p>
          <el-upload
            v-if="canEdit"
            class="photo-upload-inline"
            :show-file-list="false"
            :auto-upload="false"
            accept="image/jpeg,image/png,image/webp"
            :on-change="file => $emit('upload-photo', { member, file })"
          >
            <el-button size="small" plain>{{ member.photoUrl ? '更换照片' : '上传照片' }}</el-button>
          </el-upload>
        </div>
      </section>

      <el-alert
        v-if="isBasicVisible"
        class="basic-visibility-alert"
        type="info"
        show-icon
        :closable="false"
        title="该成员属于堂/表亲关系基础可见范围，仅展示姓名、世代、性别、支系等关系信息，完整档案未开放。"
      />

      <section class="archive-completion-card" v-if="!isBasicVisible">
        <div class="completion-head">
          <span>档案完整度</span>
          <strong>{{ completeness.score }}%</strong>
        </div>
        <el-progress
          :percentage="completeness.score"
          :stroke-width="8"
          :status="completionStatus(completeness.score)"
        />
        <div v-if="completeness.missing.length" class="missing-fields">
          <span>建议补全：</span>
          <el-tag v-for="field in completeness.missing.slice(0, 8)" :key="field" size="small" type="warning" effect="plain">
            {{ field }}
          </el-tag>
        </div>
        <div v-else class="complete-tip">核心档案已较完整，可继续补充传略和资料来源。</div>
      </section>

      <section class="archive-section">
        <div class="archive-section-title">
          <span>一、姓名身份</span>
          <small>Identity</small>
        </div>
        <div class="archive-grid two">
          <InfoItem label="姓名" :value="member.name" highlight />
          <InfoItem label="性别" :value="member.gender" />
          <InfoItem label="曾用名" :value="member.formerName" />
          <InfoItem label="乳名/小名" :value="member.childhoodName" />
          <InfoItem label="字" :value="member.courtesyName" />
          <InfoItem label="号" :value="member.artName" />
        </div>
      </section>

      <section class="archive-section">
        <div class="archive-section-title">
          <span>二、宗谱定位</span>
          <small>Genealogy</small>
        </div>
        <div class="archive-grid three">
          <InfoItem label="世代" :value="(member.generation !== null && member.generation !== undefined) ? `第${member.generation}代` : ''" highlight />
          <InfoItem label="字辈" :value="member.generationName" />
          <InfoItem label="排行" :value="member.rankTitle || rankText" />
          <InfoItem label="排行序号" :value="member.rankNo" />
          <InfoItem label="支系/房支" :value="member.branch" />
          <InfoItem label="公开显示" :value="member.isPublic === false ? '否' : '是'" />
          <InfoItem label="隐私级别" :value="member.privacyLabel || privacyLabel(member.privacyLevel)" />
        </div>
      </section>

      <section class="archive-section">
        <div class="archive-section-title">
          <span>三、生命轨迹</span>
          <small>Timeline</small>
        </div>
        <div class="life-strip">
          <div>
            <b>{{ dateSummary(member, 'birth') }}</b>
            <span>出生 · {{ display(member.birthPlace, '地点不详') }}</span>
          </div>
          <div>
            <b>{{ member.isLiving === false ? dateSummary(member, 'death') : '健在' }}</b>
            <span>{{ member.isLiving === false ? `去世 · ${display(member.deathPlace, '地点不详')}` : display(member.residence || member.currentResidence, '现居未记录') }}</span>
          </div>
        </div>
        <el-timeline class="archive-timeline">
          <el-timeline-item :timestamp="dateSummary(member, 'birth', '年份不详')" type="success">
            出生于 {{ display(member.birthPlace, '地点不详') }}<span v-if="dateOriginal(member, 'birth')">；原文：{{ dateOriginal(member, 'birth') }}</span>
          </el-timeline-item>
          <el-timeline-item v-if="spouseDisplay || member.marriageNote || effectiveMarriageYear" :timestamp="display(effectiveMarriageYear, '年份不详')" type="warning">
            婚配：{{ display(spouseDisplay, '未记录配偶') }}<span v-if="member.marriageNote">；{{ member.marriageNote }}</span>
          </el-timeline-item>
          <el-timeline-item v-if="showMigration" :timestamp="display(member.migrateDate, '年份不详')">
            迁居 / 居住：{{ display(member.residence || member.currentResidence, '未记录') }}
          </el-timeline-item>
          <el-timeline-item v-if="member.isLiving === false || member.deathDate || member.died || member.deathLunarDate || member.deathDateText" :timestamp="dateSummary(member, 'death', '年份不详')" type="info">
            去世于 {{ display(member.deathPlace, '地点不详') }}<span v-if="member.burialPlace">；葬于 {{ member.burialPlace }}</span><span v-if="dateOriginal(member, 'death')">；原文：{{ dateOriginal(member, 'death') }}</span>
          </el-timeline-item>
        </el-timeline>
      </section>

      <section class="archive-section">
        <div class="archive-section-title">
          <span>四、亲属关系</span>
          <small>Family</small>
        </div>
        <div class="mini-relation-tree">
          <!-- 第一代：父母 -->
          <div class="tree-tier tier-parents">
            <div class="tree-node-wrapper">
              <button v-if="fatherMember" class="mini-tree-node" type="button" @click="jumpToMember(fatherMember.id)">
                <span class="node-relation">父亲</span>
                <span class="node-name">{{ fatherMember.name }}</span>
              </button>
              <div v-else class="mini-tree-node empty">
                <span class="node-relation">父亲</span>
                <span class="node-name">未记录</span>
              </div>
            </div>
            <div class="tree-node-wrapper">
              <button v-if="motherMember" class="mini-tree-node" type="button" @click="jumpToMember(motherMember.id)">
                <span class="node-relation">母亲</span>
                <span class="node-name">{{ motherMember.name }}</span>
              </button>
              <div v-else class="mini-tree-node empty">
                <span class="node-relation">母亲</span>
                <span class="node-name">未记录</span>
              </div>
            </div>
          </div>

          <!-- 代际垂直连接线 -->
          <div class="tree-connector vertical"></div>

          <!-- 第二代：当前成员及配偶 -->
          <div class="tree-tier tier-current">
            <div class="tree-node-wrapper active">
              <div class="mini-tree-node current-node">
                <span class="node-relation">当前成员</span>
                <span class="node-name">{{ member.name }}</span>
              </div>
            </div>
            
            <!-- 配偶组 -->
            <div class="spouses-group" v-if="spouseMembers.length">
              <div class="tree-connector horizontal"></div>
              <div class="spouse-nodes">
                <button v-for="sp in spouseMembers" :key="sp.id" class="mini-tree-node spouse-node" type="button" @click="jumpToMember(sp.id)">
                  <span class="node-relation">配偶</span>
                  <span class="node-name">{{ sp.name }}</span>
                </button>
              </div>
            </div>
            <div class="spouses-group empty" v-else-if="member.spouse">
              <div class="tree-connector horizontal"></div>
              <div class="mini-tree-node spouse-node empty">
                <span class="node-relation">配偶 (未建档)</span>
                <span class="node-name">{{ member.spouse }}</span>
              </div>
            </div>
          </div>

          <!-- 代际垂直连接线 -->
          <div class="tree-connector vertical"></div>

          <!-- 第三代：子女 -->
          <div class="tree-tier tier-children">
            <template v-if="childrenMembers.length">
              <button v-for="child in childrenMembers" :key="child.id" class="mini-tree-node child-node" type="button" @click="jumpToMember(child.id)">
                <span class="node-relation">子女</span>
                <span class="node-name">{{ child.name }}</span>
              </button>
            </template>
            <div v-else-if="member.childrenNote" class="mini-tree-node empty wide-node">
              <span class="node-relation">子女备注</span>
              <span class="node-name">{{ member.childrenNote }}</span>
            </div>
            <div v-else class="mini-tree-node empty">
              <span class="node-relation">子女</span>
              <span class="node-name">未记录</span>
            </div>
          </div>
        </div>
        <div v-if="member.marriageNote" class="archive-note-list" style="margin-top: 10px;">
          <p><b>婚配说明：</b>{{ member.marriageNote }}</p>
        </div>
      </section>

      <section class="archive-section">
        <div class="archive-section-title">
          <span>五、人物档案</span>
          <small>Biography</small>
        </div>
        <div class="archive-grid three">
          <InfoItem label="学历" :value="member.education" />
          <InfoItem label="职业" :value="member.occupation" />
          <InfoItem label="职务/身份" :value="member.positionTitle" />
          <InfoItem label="祖籍/籍贯" :value="member.ancestralOrigin" />
          <InfoItem label="现居住地" :value="member.residence || member.currentResidence" />
          <div class="archive-info-item burial-map-item">
            <small>安葬地/墓址</small>
            <b>{{ display(member.burialPlace) }}</b>
            <div v-if="member.burialLat && member.burialLng" class="coordinate-line">
              坐标：{{ Number(member.burialLat).toFixed(6) }}, {{ Number(member.burialLng).toFixed(6) }}
            </div>
            <a
              v-if="burialMapUrl"
              class="map-link"
              :href="burialMapUrl"
              target="_blank"
              rel="noopener noreferrer"
            >打开地图定位</a>
          </div>
        </div>
        <div class="bio-card">
          <small>人物简介 / 传略</small>
          <p>{{ display(member.biography, '暂未记录人物传略。可补充教育经历、职业贡献、迁徙经历、家庭事迹等。') }}</p>
        </div>
        <div class="source-card">
          <small>资料来源</small>
          <p>{{ display(sourceDisplay, '暂未记录资料来源。建议按“来源类型｜提供人/载体｜时间｜备注”格式补充。') }}</p>
          <div class="source-spec-line">推荐格式：来源类型｜提供人/载体｜时间｜备注</div>
        </div>
        <div v-if="canViewSource" class="source-card citation-card">
          <div class="citation-card-head">
            <small>结构化引用记录</small>
            <el-button size="small" link type="primary" @click="emit('refresh-citations', member.id)">刷新</el-button>
          </div>
          <el-table
            v-loading="citationLoading"
            :data="citations"
            size="small"
            max-height="220"
            empty-text="暂无引用记录"
          >
            <el-table-column prop="sourceTitle" label="来源" min-width="150" show-overflow-tooltip />
            <el-table-column label="字段" width="100" show-overflow-tooltip>
              <template #default="{ row }">{{ citationFieldLabel(row.fieldName) }}</template>
            </el-table-column>
            <el-table-column prop="quoteText" label="摘录" min-width="160" show-overflow-tooltip />
          </el-table>
          <div v-if="canManageSources" class="citation-form">
            <el-select v-model="citationDraft.source_id" filterable clearable size="small" placeholder="选择来源" class="citation-form-source">
              <el-option v-for="source in sourceOptions" :key="source.id" :label="sourceOptionLabel(source)" :value="source.id" />
            </el-select>
            <el-select v-model="citationDraft.field_name" clearable size="small" placeholder="佐证字段" class="citation-form-field">
              <el-option v-for="item in citationFieldOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-input v-model="citationDraft.quote_text" size="small" placeholder="摘录/说明，可选" class="citation-form-quote" />
            <el-button type="primary" size="small" :disabled="!citationDraft.source_id" @click="saveCitation">添加引用</el-button>
          </div>
          <div v-if="canManageSources && !sourceOptions.length" class="source-spec-line">请先在“系统设置 → 来源/GEDCOM”中新增来源。</div>
        </div>
      </section>

      <section v-if="canViewSource" class="archive-section archive-maintenance">
        <div class="archive-section-title">
          <span>六、资料维护</span>
          <small>Source</small>
        </div>
        <div class="archive-grid two">
          <InfoItem label="来源规范" :value="sourceFormatHint" />
          <InfoItem label="档案状态" :value="archiveStatus" />
        </div>
      </section>
    </div>

    <template v-if="member" #footer>
      <div class="drawer-footer-actions">
        <el-button plain type="warning" @click="$emit('locate-member', member.id)">在家谱中定位</el-button>
        <el-button v-if="canEdit" type="primary" @click="$emit('edit-member', member)">编辑补全</el-button>
        <el-button v-if="canDelete" type="danger" plain @click="$emit('delete-member', member)">删除</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch, onUnmounted } from 'vue'
import { fetchAuthenticatedObjectUrl, revokeObjectUrl } from '../utils/authenticatedAsset'

function privacyLabel(level) {
  return { public: '公开', login: '登录可见', branch: '本分支可见', admin: '仅管理员可见' }[level] || '公开'
}

function display(value, fallback = '未记录') {
  if (value === null || value === undefined) return fallback
  const text = String(value).trim()
  return text === '' ? fallback : text
}

function dateOriginal(member, prefix) {
  return display(member?.[`${prefix}DateText`], '')
}

function dateSummary(member, prefix, fallback = prefix === 'birth' ? '生年不详' : '卒年不详') {
  const solar = display(member?.[`${prefix}Date`] || (prefix === 'birth' ? member?.born : member?.died), '')
  const lunarRaw = display(member?.[`${prefix}LunarDate`], '')
  const leap = member?.[`${prefix}IsLeapMonth`] === true ? '闰月 · ' : ''
  const lunar = lunarRaw ? `${leap}${lunarRaw}` : ''
  const cal = member?.[`${prefix}Calendar`] || ''
  if (solar && lunar) return `阳历 ${solar} / 阴历 ${lunar}`
  if (cal === 'lunar' && lunar) return `阴历 ${lunar}`
  if (solar) return `阳历 ${solar}`
  if (lunar) return `阴历 ${lunar}`
  return display(member?.[`${prefix}DateText`], fallback)
}

const InfoItem = defineComponent({
  name: 'InfoItem',
  props: {
    label: { type: String, required: true },
    value: { type: [String, Number, Boolean], default: '' },
    highlight: { type: Boolean, default: false },
  },
  setup(props) {
    return () => h('div', { class: ['archive-info-item', props.highlight ? 'highlight' : ''] }, [
      h('small', props.label),
      h('b', display(props.value)),
    ])
  },
})

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  member: { type: Object, default: null },
  allMembers: { type: Array, default: () => [] },
  sources: { type: Array, default: () => [] },
  citations: { type: Array, default: () => [] },
  citationLoading: { type: Boolean, default: false },
  canEdit: { type: Boolean, default: false },
  canDelete: { type: Boolean, default: false },
  canViewSource: { type: Boolean, default: false },
  canManageSources: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'edit-member', 'delete-member', 'open-member', 'locate-member', 'upload-photo', 'refresh-citations', 'create-citation'])
const canEdit = computed(() => props.canEdit && !isBasicVisible.value)
const isBasicVisible = computed(() => props.member?.visibilityScope === 'basic')
const canDelete = computed(() => props.canDelete)
const canViewSource = computed(() => props.canViewSource)
const canManageSources = computed(() => props.canManageSources)
const authenticatedPhotoUrl = ref('')

watch(() => props.member?.photoUrl, async (url) => {
  revokeObjectUrl(authenticatedPhotoUrl.value)
  authenticatedPhotoUrl.value = ''
  if (!url) return
  try {
    authenticatedPhotoUrl.value = await fetchAuthenticatedObjectUrl(url)
  } catch {
    authenticatedPhotoUrl.value = ''
  }
}, { immediate: true })

onUnmounted(() => revokeObjectUrl(authenticatedPhotoUrl.value))

const visibleModel = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const completenessFields = [
  { key: 'name', label: '姓名', required: true },
  { key: 'gender', label: '性别', required: true },
  { key: 'generation', label: '世代', required: true },
  { key: 'generationName', label: '字辈' },
  { key: 'rankTitle', label: '排行' },
  { key: 'branch', label: '支系' },
  { key: 'birthDate', altKeys: ['birthLunarDate', 'birthDateText'], label: '出生日期' },
  { key: 'birthPlace', label: '出生地' },
  { key: 'residence', altKeys: ['currentResidence'], label: '现居住地' },
  { key: 'ancestralOrigin', label: '祖籍' },
  { key: 'fatherName', label: '父亲' },
  { key: 'motherName', label: '母亲' },
  { key: 'spouse', altKeys: ['spouseName'], label: '配偶' },
  { key: 'source', label: '资料来源' },
  { key: 'biography', label: '传略' },
]

function fieldValue(member, field) {
  const keys = [field.key, ...(field.altKeys || [])]
  for (const key of keys) {
    const value = member?.[key]
    if (value !== null && value !== undefined && String(value).trim() !== '') return value
  }
  return ''
}

const completeness = computed(() => {
  if (!props.member) return { score: 0, missing: [] }
  const missing = completenessFields.filter(field => !fieldValue(props.member, field)).map(field => field.label)
  const filled = completenessFields.length - missing.length
  return { score: Math.round((filled / completenessFields.length) * 100), missing }
})

function completionStatus(score) {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'exception'
}

const initial = computed(() => display(props.member?.name, '人').slice(0, 1))

const identityLine = computed(() => {
  const m = props.member || {}
  return [
    m.occupation || m.positionTitle,
    m.birthPlace || m.ancestralOrigin,
    m.residence || m.currentResidence,
  ].filter(Boolean).join(' · ') || '身份、生平与居住信息待补充'
})

const rankText = computed(() => {
  const m = props.member || {}
  return m.rankNo ? `第${m.rankNo}` : ''
})

const archiveStatus = computed(() => {
  if (completeness.value.score >= 85) return '完整'
  if (completeness.value.score >= 65) return '待补细节'
  return '重点补全'
})

const sourceDisplay = computed(() => {
  const raw = String(props.member?.source || '').trim()
  if (!raw) return ''
  return raw
})

const sourceFormatHint = computed(() => '来源类型｜提供人/载体｜时间｜备注')
const burialMapUrl = computed(() => {
  const lat = props.member?.burialLat
  const lng = props.member?.burialLng
  const place = String(props.member?.burialPlace || '').trim()
  if (lat && lng) {
    return `https://uri.amap.com/marker?position=${lng},${lat}&name=${encodeURIComponent(place || '安葬地')}`
  }
  return place ? `https://uri.amap.com/search?keyword=${encodeURIComponent(place)}` : ''
})

const showMigration = computed(() => {
  const migrateDate = props.member?.migrateDate?.trim?.() || ''
  const currentResidence = props.member?.currentResidence?.trim?.() || props.member?.residence?.trim?.() || ''
  const birthPlace = props.member?.birthPlace?.trim?.() || ''
  return Boolean(migrateDate || (currentResidence && currentResidence !== birthPlace))
})

function findMemberById(id) {
  const target = Number(id)
  if (!Number.isFinite(target)) return null
  return (props.allMembers || []).find(m => Number(m.id) === target) || null
}

const fatherMember = computed(() => {
  return findMemberById(props.member?.fatherId) || 
         (props.member?.fatherName ? (props.allMembers || []).find(m => m.name === props.member.fatherName.trim()) : null) || 
         null
})
const motherMember = computed(() => {
  return findMemberById(props.member?.motherId) || 
         (props.member?.motherName ? (props.allMembers || []).find(m => m.name === props.member.motherName.trim()) : null) || 
         null
})
const spouseMembers = computed(() => {
  const directIds = Array.isArray(props.member?.spouseIds) ? props.member.spouseIds : []
  const direct = directIds.map(findMemberById).filter(Boolean)
  
  if (direct.length === 0 && props.member?.spouse) {
    const names = props.member.spouse.split(/[、,，]/).map(n => n.trim()).filter(Boolean)
    for (const name of names) {
      const match = (props.allMembers || []).find(m => m.name === name)
      if (match) direct.push(match)
    }
  }

  const selfId = Number(props.member?.id)
  if (Number.isFinite(selfId)) {
    for (const candidate of props.allMembers || []) {
      const ids = Array.isArray(candidate?.spouseIds) ? candidate.spouseIds.map(Number) : []
      if (ids.includes(selfId) && !direct.some(m => Number(m.id) === Number(candidate.id))) {
        direct.push(candidate)
      }
    }
  }
  return direct
})
const spouseDisplay = computed(() => spouseMembers.value.map(m => m.name).filter(Boolean).join('、') || props.member?.spouse || '')
const effectiveMarriageYear = computed(() => {
  const own = display(props.member?.marriageYear, '')
  if (own) return own
  const spouseWithYear = spouseMembers.value.find(m => display(m?.marriageYear, ''))
  return spouseWithYear ? display(spouseWithYear.marriageYear, '') : ''
})
const childrenMembers = computed(() => {
  const selfId = Number(props.member?.id)
  if (!Number.isFinite(selfId)) return []
  return (props.allMembers || []).filter(m => Number(m.fatherId) === selfId || Number(m.motherId) === selfId)
})

const sourceOptions = computed(() => (props.sources || []).filter(source => source?.id))
const citationDraft = reactive({ source_id: null, field_name: '', quote_text: '', note: '' })
const citationFieldOptions = [
  { value: 'name', label: '姓名' },
  { value: 'birth_date', label: '出生' },
  { value: 'death_date', label: '去世' },
  { value: 'father_id', label: '父亲关系' },
  { value: 'mother_id', label: '母亲关系' },
  { value: 'spouse_ids', label: '配偶关系' },
  { value: 'biography', label: '传略' },
  { value: 'source', label: '来源说明' },
]

function citationFieldLabel(value) {
  if (!value) return '通用'
  return citationFieldOptions.find(item => item.value === value)?.label || value
}

function sourceOptionLabel(source) {
  return [source?.title, source?.sourceType, source?.reference].filter(Boolean).join(' · ')
}

function resetCitationDraft() {
  citationDraft.source_id = null
  citationDraft.field_name = ''
  citationDraft.quote_text = ''
  citationDraft.note = ''
}

function saveCitation() {
  if (!props.member?.id || !citationDraft.source_id) return
  emit('create-citation', {
    memberId: props.member.id,
    payload: {
      source_id: citationDraft.source_id,
      field_name: citationDraft.field_name || null,
      quote_text: citationDraft.quote_text || null,
      note: citationDraft.note || null,
    },
    done: resetCitationDraft,
  })
}

function jumpToMember(memberOrId) {
  if (memberOrId === null || memberOrId === undefined) return
  emit('open-member', memberOrId)
}
</script>


<style scoped>
.citation-card { margin-top: 12px; }
.citation-card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.citation-form { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; align-items: center; }
.citation-form-source { min-width: 190px; flex: 1 1 190px; }
.citation-form-field { width: 130px; }
.citation-form-quote { min-width: 180px; flex: 1 1 180px; }

/* 微型直系三代关系树样式 */
.mini-relation-tree {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  background: color-mix(in srgb, var(--bg) 35%, transparent);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  margin-top: 10px;
  box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.01);
}

.tree-tier {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.tier-parents {
  margin-bottom: 2px;
}

.tier-current {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24px;
}

.spouses-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spouse-nodes {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tier-children {
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 2px;
}

.mini-tree-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 130px;
  height: 52px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--card-bg);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
  text-align: center;
  box-shadow: 0 2px 4px rgba(62, 44, 28, 0.04);
}

.mini-tree-node:hover:not(.empty) {
  transform: translateY(-1px);
  border-color: var(--primary);
  box-shadow: 0 4px 8px rgba(139, 69, 19, 0.12);
}

.mini-tree-node.empty {
  cursor: default;
  background: color-mix(in srgb, var(--bg) 50%, transparent);
  border-style: dashed;
  box-shadow: none;
}

.mini-tree-node.empty .node-name {
  color: var(--text-secondary);
  font-style: italic;
  font-weight: normal;
}

.current-node {
  border: 2px solid var(--primary);
  background: color-mix(in srgb, var(--primary) 8%, var(--card-bg));
  cursor: default;
}

.node-relation {
  font-size: 10px;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 2px;
}

.node-name {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.current-node .node-name {
  color: var(--primary);
}

/* 连接线 */
.tree-connector.vertical {
  width: 2px;
  height: 14px;
  background-color: var(--border);
}

.tree-connector.horizontal {
  width: 16px;
  height: 2px;
  background-color: var(--border);
}

/* 当配偶节点为空或特殊节点时的样式 */
.spouses-group.empty .mini-tree-node.empty {
  width: 100px;
}

.wide-node {
  width: 260px;
}
</style>
