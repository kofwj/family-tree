<template>
  <el-dialog
    v-model="visibleModel"
    :title="isEdit ? `编辑成员 · ${form.name}` : '新增成员'"
    width="760px"
    destroy-on-close
  >
    <div class="member-form-shell">
      <div class="member-form-intro">
        <strong>字段分层说明</strong>
        <p>本表单已按身份核心、关系结构、人物档案、系统控制分层。涉及家谱骨架的结构字段需要更高权限。</p>
      </div>

      <el-form :model="form" label-width="80px" label-position="top" class="member-form">
        <el-divider content-position="left">身份核心层</el-divider>
        <div class="field-group-tip">用于识别成员身份与家族中的基础位置。</div>
        <div class="photo-form-card">
          <div class="photo-form-preview" :class="form.gender === '女' ? 'female' : 'male'">
            <img v-if="effectivePhotoPreview" :src="effectivePhotoPreview" :alt="`${form.name || '成员'}照片`" />
            <span v-else>{{ (form.name || '未').slice(0, 1) }}</span>
          </div>
          <div class="photo-form-actions">
            <strong>成员照片</strong>
            <p>可在编辑资料时直接上传或更换照片，保存资料后同步生效。</p>
            <el-upload
              :show-file-list="false"
              :auto-upload="false"
              accept="image/jpeg,image/png,image/webp"
              :on-change="onPhotoChange"
            >
              <el-button size="small" plain>{{ effectivePhotoPreview ? '更换照片' : '上传照片' }}</el-button>
            </el-upload>
            <el-button v-if="photoPreviewUrl" link type="danger" size="small" @click="clearSelectedPhoto">取消本次选择</el-button>
          </div>
        </div>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="姓名" required><el-input v-model="form.name" placeholder="必填" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="曾用名"><el-input v-model="form.formerName" placeholder="如：原名、旧名" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="乳名/小名"><el-input v-model="form.childhoodName" placeholder="如：小名" /></el-form-item></el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="字"><el-input v-model="form.courtesyName" placeholder="如：字某某" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="号"><el-input v-model="form.artName" placeholder="如：号某某" /></el-form-item></el-col>
          <el-col :span="8">
            <el-form-item label="性别">
              <el-radio-group v-model="form.gender" @change="maybeSyncRankTitle"><el-radio label="男">男</el-radio><el-radio label="女">女</el-radio></el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">关系结构层</el-divider>
        <div class="field-group-tip field-group-tip--warning">以下字段会影响家谱骨架与主线结构。<span v-if="!canEditCoreRelation"> 当前账号仅可查看，不可修改这些字段。</span></div>
        <el-row :gutter="16">
          <el-col :span="6"><el-form-item label="世代"><el-input-number v-model="form.generation" :min="1" :max="50" controls-position="right" style="width:100%" :disabled="!canEditCoreRelation" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="字辈"><el-input v-model="form.generationName" placeholder="如：文、金" :disabled="!canEditCoreRelation" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="排行序号"><el-input-number v-model="form.rankNo" :min="1" :max="99" controls-position="right" style="width:100%" @change="maybeSyncRankTitle" :disabled="!canEditCoreRelation" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="排行"><el-input v-model="form.rankTitle" placeholder="如：长子、次女" @input="rankTitleTouched = true" :disabled="!canEditCoreRelation" /></el-form-item></el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="支系/房支"><el-input v-model="form.branch" placeholder="如：长房、二房、某某支" :disabled="!canEditCoreRelation" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="本族主线"><el-switch v-model="form.isCoreMember" active-text="是" inactive-text="否" :disabled="!canEditCoreRelation" /></el-form-item></el-col>
        </el-row>

        <el-form-item label="配偶">
          <el-select v-model="form.spouseIds" filterable multiple clearable placeholder="选择配偶（支持多选）" style="width:100%" :disabled="!canEditCoreRelation">
            <el-option v-for="m in relationOptions" :key="m.id" :label="`${m.name}（#${m.id} · 第${m.generation || '?'}代）`" :value="m.id" />
          </el-select>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="父亲">
              <el-select v-model="form.fatherId" filterable clearable placeholder="选择父亲" style="width:100%" :disabled="!canEditCoreRelation">
                <el-option v-for="m in relationOptions" :key="m.id" :label="`${m.name}（#${m.id} · 第${m.generation || '?'}代）`" :value="m.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="母亲">
              <el-select v-model="form.motherId" filterable clearable placeholder="选择母亲" style="width:100%" :disabled="!canEditCoreRelation">
                <el-option v-for="m in relationOptions" :key="m.id" :label="`${m.name}（#${m.id} · 第${m.generation || '?'}代）`" :value="m.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="子女备注">
              <el-input
                :model-value="form.childrenNote"
                @update:model-value="value => form.childrenNote = value"
                placeholder="如：育有二子一女"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="婚配年份">
              <el-input
                :model-value="form.marriageYear"
                @update:model-value="value => form.marriageYear = value"
                placeholder="如：1986、约1990、年份不详"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="婚配说明">
          <el-input
            :model-value="form.marriageNote"
            @update:model-value="value => form.marriageNote = value"
            placeholder="如：原配、续弦、再婚说明"
          />
        </el-form-item>

        <el-divider content-position="left">人物档案层</el-divider>
        <div class="field-group-tip">用于承载成员生平、地域、职业、传略与资料来源。</div>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="出生日期类型">
              <el-radio-group v-model="form.birthCalendar">
                <el-radio-button label="solar">阳历</el-radio-button>
                <el-radio-button label="lunar">阴历</el-radio-button>
                <el-radio-button label="both">并轨</el-radio-button>
                <el-radio-button label="unknown">不详</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="出生阳历日期">
              <el-date-picker
                v-model="form.birthDate"
                type="date"
                value-format="YYYY-MM-DD"
                format="YYYY-MM-DD"
                placeholder="选择阳历出生日期"
                clearable
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="18">
            <el-form-item label="出生阴历日期">
              <el-input v-model="form.birthLunarDate" placeholder="如：丁酉年腊月初三 / 农历一九五八年腊月初三" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="闰月">
              <el-switch v-model="form.birthIsLeapMonth" active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="出生原始记载">
          <el-input v-model="form.birthDateText" placeholder="如：戊戌年腊月初三生；资料原文可完整保留" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="是否健在"><el-switch v-model="form.isLiving" active-text="健在" inactive-text="已故" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="出生地"><el-input v-model="form.birthPlace" placeholder="如：江苏如东" /></el-form-item></el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="去世日期类型">
              <el-radio-group v-model="form.deathCalendar" :disabled="form.isLiving">
                <el-radio-button label="solar">阳历</el-radio-button>
                <el-radio-button label="lunar">阴历</el-radio-button>
                <el-radio-button label="both">并轨</el-radio-button>
                <el-radio-button label="unknown">不详</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="去世阳历日期">
              <el-date-picker
                v-model="form.deathDate"
                type="date"
                value-format="YYYY-MM-DD"
                format="YYYY-MM-DD"
                :disabled="form.isLiving"
                placeholder="选择阳历去世日期"
                clearable
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="18">
            <el-form-item label="去世阴历日期">
              <el-input v-model="form.deathLunarDate" :disabled="form.isLiving" placeholder="如：农历庚子年正月十五" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="闰月">
              <el-switch v-model="form.deathIsLeapMonth" :disabled="form.isLiving" active-text="是" inactive-text="否" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="去世原始记载">
          <el-input v-model="form.deathDateText" :disabled="form.isLiving" placeholder="如：某年某月某日卒；资料原文可完整保留" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="去世地"><el-input v-model="form.deathPlace" :disabled="form.isLiving" placeholder="如：上海" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="现居住地"><el-input v-model="form.residence" placeholder="如：上海浦东" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="祖籍/籍贯"><el-input v-model="form.ancestralOrigin" placeholder="如：江苏如东" /></el-form-item></el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="安葬地/墓址">
              <el-input v-model="form.burialPlace" placeholder="输入墓址，或点击右侧地图选点">
                <template #append>
                  <el-button @click="openBurialMapPicker">地图选点</el-button>
                </template>
              </el-input>
              <div v-if="form.burialLat && form.burialLng" class="map-coordinate-tip">
                已定位：{{ Number(form.burialLat).toFixed(6) }}, {{ Number(form.burialLng).toFixed(6) }}
                <el-button link type="danger" size="small" @click="clearBurialLocation">清除定位</el-button>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="6"><el-form-item label="学历"><el-input v-model="form.education" placeholder="如：本科、高中" /></el-form-item></el-col>
          <el-col :span="6"><el-form-item label="职业"><el-input v-model="form.occupation" placeholder="如：教师、工程师" /></el-form-item></el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="职务/身份"><el-input v-model="form.positionTitle" placeholder="如：村支书、企业负责人" /></el-form-item></el-col>
        </el-row>

        <el-form-item label="人物简介/传略"><el-input v-model="form.biography" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="记录主要经历、贡献、迁徙、家庭事迹等" /></el-form-item>
        <el-form-item label="资料来源">
          <el-input v-model="form.source" type="textarea" :rows="3" maxlength="300" show-word-limit placeholder="推荐填写：来源类型｜提供人/载体｜时间｜备注" />
          <div class="field-group-tip source-spec-tip">推荐统一填写格式：来源类型｜提供人/载体｜时间｜备注。来源类型优先使用：口述、纸谱、墓碑、户籍、讣告、访谈、微信记录。</div>
        </el-form-item>

        <el-divider content-position="left">系统控制层</el-divider>
        <div class="field-group-tip">用于控制成员对外展示与后续治理策略。</div>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="公开显示"><el-switch v-model="form.isPublic" active-text="是" inactive-text="否" /></el-form-item></el-col>
          <el-col :span="12">
            <el-form-item label="隐私级别">
              <el-select v-model="form.privacyLevel" style="width:100%">
                <el-option label="公开" value="public" />
                <el-option label="登录可见" value="login" />
                <el-option label="本分支可见" value="branch" />
                <el-option label="仅管理员可见" value="admin" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </div>

    <el-dialog v-model="mapPickerVisible" title="选择安葬地图定位" width="860px" append-to-body destroy-on-close @opened="initBurialMap">
      <div class="map-picker-toolbar">
        <el-input v-model="mapSearchKeyword" placeholder="输入墓址/公墓/村镇搜索，例如：如东三桥村" clearable @keyup.enter="searchBurialPlace" />
        <el-button type="primary" :loading="mapSearching" @click="searchBurialPlace">搜索定位</el-button>
        <el-button @click="useBrowserLocation">用当前位置</el-button>
      </div>
      <div class="map-picker-tip">可搜索后在地图上点击精确位置；保存后会同时写入安葬地址、纬度、经度。</div>
      <div ref="mapEl" class="map-picker-canvas"></div>
      <div class="map-picker-result">
        <span>选中地址：{{ mapSelectedAddress || '尚未选择' }}</span>
        <span v-if="mapSelectedLat && mapSelectedLng">坐标：{{ Number(mapSelectedLat).toFixed(6) }}, {{ Number(mapSelectedLng).toFixed(6) }}</span>
      </div>
      <template #footer>
        <el-button @click="mapPickerVisible = false">取消</el-button>
        <el-button type="primary" :disabled="!mapSelectedLat || !mapSelectedLng" @click="applyBurialMapSelection">使用此定位</el-button>
      </template>
    </el-dialog>

    <template #footer>
      <el-button @click="visibleModel = false">取消</el-button>
      <el-button type="primary" @click="submit" :loading="saving">{{ isEdit ? '保存' : '新增' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  member: { type: Object, default: null },
  allMembers: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
  canEditCoreRelation: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'submit', 'upload-photo'])

const visibleModel = computed({ get: () => props.modelValue, set: (val) => emit('update:modelValue', val) })
const isEdit = computed(() => !!props.member?.id)
const rankTitleTouched = ref(false)
const selectedPhotoFile = ref(null)
const photoPreviewUrl = ref('')
const effectivePhotoPreview = computed(() => photoPreviewUrl.value || form.value.photoUrl || '')

function revokePhotoPreview() {
  if (photoPreviewUrl.value) {
    URL.revokeObjectURL(photoPreviewUrl.value)
    photoPreviewUrl.value = ''
  }
}

function onPhotoChange(uploadFile) {
  const raw = uploadFile?.raw
  if (!raw) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(raw.type)) {
    ElMessage.error('仅支持 JPG/PNG/WebP 照片')
    return
  }
  revokePhotoPreview()
  selectedPhotoFile.value = raw
  photoPreviewUrl.value = URL.createObjectURL(raw)
}

function clearSelectedPhoto() {
  selectedPhotoFile.value = null
  revokePhotoPreview()
}

function rankTitleByNo(rankNo, gender) {
  const n = Number(rankNo)
  if (!Number.isFinite(n) || n <= 0) return ''
  if (n === 1) return gender === '女' ? '长女' : '长子'
  if (n === 2) return gender === '女' ? '次女' : '次子'
  const cnNums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
  const prefix = n <= 10 ? cnNums[n] : String(n)
  return `${prefix}${gender === '女' ? '女' : '子'}`
}

function maybeSyncRankTitle() {
  if (rankTitleTouched.value) return
  form.value.rankTitle = rankTitleByNo(form.value.rankNo, form.value.gender)
}

const defaultForm = () => ({
  name: '', formerName: '', courtesyName: '', artName: '', childhoodName: '', gender: '男',
  generation: null, generationName: '', rankNo: null, rankTitle: '', branch: '', isCoreMember: true,
  birthPlace: '', deathPlace: '', residence: '', ancestralOrigin: '', burialPlace: '', burialLat: null, burialLng: null,
  birthDate: '', birthCalendar: 'solar', birthLunarDate: '', birthIsLeapMonth: false, birthDateText: '',
  deathDate: '', deathCalendar: 'solar', deathLunarDate: '', deathIsLeapMonth: false, deathDateText: '',
  isLiving: true, spouseIds: [], fatherId: null, motherId: null, childrenNote: '', marriageYear: '', marriageNote: '',
  education: '', occupation: '', positionTitle: '', biography: '', source: '', isPublic: true,
})

const form = ref(defaultForm())
const relationOptions = computed(() => (props.allMembers || []).filter(m => m.id !== props.member?.id))

function memberToForm(member) {
  return {
    ...defaultForm(),
    name: member.name || '',
    formerName: member.formerName || '',
    courtesyName: member.courtesyName || '',
    artName: member.artName || '',
    childhoodName: member.childhoodName || '',
    gender: member.gender || '男',
    generation: member.generation ?? null,
    generationName: member.generationName || '',
    rankNo: member.rankNo ?? null,
    rankTitle: member.rankTitle || '',
    branch: member.branch || '',
    isCoreMember: member.isCoreMember !== false,
    birthPlace: member.birthPlace || '',
    deathPlace: member.deathPlace || '',
    residence: member.residence || '',
    ancestralOrigin: member.ancestralOrigin || '',
    burialPlace: member.burialPlace || '',
    burialLat: member.burialLat ?? null,
    burialLng: member.burialLng ?? null,
    photoUrl: member.photoUrl || '',
    birthDate: member.birthDate || '',
    birthCalendar: member.birthCalendar || 'solar',
    birthLunarDate: member.birthLunarDate || '',
    birthIsLeapMonth: member.birthIsLeapMonth === true,
    birthDateText: member.birthDateText || '',
    deathDate: member.deathDate || '',
    deathCalendar: member.deathCalendar || 'solar',
    deathLunarDate: member.deathLunarDate || '',
    deathIsLeapMonth: member.deathIsLeapMonth === true,
    deathDateText: member.deathDateText || '',
    isLiving: member.isLiving !== false && !member.deathDate,
    spouseIds: Array.isArray(member.spouseIds) ? member.spouseIds : [],
    fatherId: member.fatherId ?? null,
    motherId: member.motherId ?? null,
    childrenNote: member.childrenNote || '',
    marriageYear: member.marriageYear || '',
    marriageNote: member.marriageNote || '',
    education: member.education || '',
    occupation: member.occupation || '',
    positionTitle: member.positionTitle || '',
    biography: member.biography || '',
    source: member.source || '',
    isPublic: member.isPublic !== false,
    privacyLevel: member.privacyLevel || 'public',
  }
}

watch(() => props.modelValue, (val) => {
  if (val) {
    rankTitleTouched.value = false
    selectedPhotoFile.value = null
    revokePhotoPreview()
    form.value = props.member?.id ? memberToForm(props.member) : defaultForm()
    if (!form.value.rankTitle && form.value.rankNo) maybeSyncRankTitle()
  } else {
    selectedPhotoFile.value = null
    revokePhotoPreview()
  }
})


const mapPickerVisible = ref(false)
const mapEl = ref(null)
const mapSearchKeyword = ref('')
const mapSearching = ref(false)
const mapSelectedAddress = ref('')
const mapSelectedLat = ref(null)
const mapSelectedLng = ref(null)
let leafletPromise = null
let leafletMap = null
let leafletMarker = null

function hasWindow() {
  return typeof window !== 'undefined' && typeof document !== 'undefined'
}

function loadLeaflet() {
  if (!hasWindow()) return Promise.reject(new Error('当前环境不支持地图'))
  if (window.L) return Promise.resolve(window.L)
  if (leafletPromise) return leafletPromise
  leafletPromise = new Promise((resolve, reject) => {
    const cssId = 'leaflet-css'
    if (!document.getElementById(cssId)) {
      const link = document.createElement('link')
      link.id = cssId
      link.rel = 'stylesheet'
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
      document.head.appendChild(link)
    }
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.async = true
    script.onload = () => resolve(window.L)
    script.onerror = () => reject(new Error('地图组件加载失败'))
    document.body.appendChild(script)
  })
  return leafletPromise
}

function openBurialMapPicker() {
  mapSearchKeyword.value = form.value.burialPlace || ''
  mapSelectedAddress.value = form.value.burialPlace || ''
  mapSelectedLat.value = form.value.burialLat || null
  mapSelectedLng.value = form.value.burialLng || null
  mapPickerVisible.value = true
}

async function initBurialMap() {
  try {
    await nextTick()
    const L = await loadLeaflet()
    const lat = Number(mapSelectedLat.value) || 32.33
    const lng = Number(mapSelectedLng.value) || 121.18
    if (leafletMap) {
      leafletMap.remove()
      leafletMap = null
      leafletMarker = null
    }
    leafletMap = L.map(mapEl.value).setView([lat, lng], mapSelectedLat.value && mapSelectedLng.value ? 15 : 11)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(leafletMap)
    leafletMap.on('click', async (event) => {
      await setMapSelection(event.latlng.lat, event.latlng.lng, '')
    })
    if (mapSelectedLat.value && mapSelectedLng.value) {
      setMarker(Number(mapSelectedLat.value), Number(mapSelectedLng.value))
    } else if (mapSearchKeyword.value) {
      setTimeout(searchBurialPlace, 300)
    }
  } catch (e) {
    ElMessage.error(e.message || '地图加载失败')
  }
}

function setMarker(lat, lng) {
  if (!leafletMap || !window.L) return
  if (!leafletMarker) leafletMarker = window.L.marker([lat, lng]).addTo(leafletMap)
  else leafletMarker.setLatLng([lat, lng])
  leafletMap.setView([lat, lng], Math.max(leafletMap.getZoom(), 15))
}

async function reverseGeocode(lat, lng) {
  try {
    const url = `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lng)}&accept-language=zh-CN`
    const res = await fetch(url)
    if (!res.ok) return ''
    const data = await res.json()
    return data?.display_name || ''
  } catch {
    return ''
  }
}

async function setMapSelection(lat, lng, address = '') {
  mapSelectedLat.value = lat
  mapSelectedLng.value = lng
  setMarker(lat, lng)
  mapSelectedAddress.value = address || await reverseGeocode(lat, lng) || mapSearchKeyword.value || form.value.burialPlace || ''
}

async function searchBurialPlace() {
  const keyword = String(mapSearchKeyword.value || '').trim()
  if (!keyword) return
  mapSearching.value = true
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(keyword)}&accept-language=zh-CN`
    const res = await fetch(url)
    if (!res.ok) throw new Error('地图搜索失败')
    const items = await res.json()
    if (!items?.length) {
      ElMessage.warning('没有搜索到位置，可在地图上手动点击选择')
      return
    }
    const item = items[0]
    await setMapSelection(Number(item.lat), Number(item.lon), item.display_name || keyword)
  } catch (e) {
    ElMessage.error(e.message || '地图搜索失败')
  } finally {
    mapSearching.value = false
  }
}

function useBrowserLocation() {
  if (!navigator.geolocation) {
    ElMessage.warning('当前浏览器不支持定位')
    return
  }
  navigator.geolocation.getCurrentPosition(
    async pos => setMapSelection(pos.coords.latitude, pos.coords.longitude, '当前位置'),
    () => ElMessage.error('无法获取当前位置')
  )
}

function applyBurialMapSelection() {
  form.value.burialPlace = mapSelectedAddress.value || mapSearchKeyword.value || form.value.burialPlace
  form.value.burialLat = mapSelectedLat.value
  form.value.burialLng = mapSelectedLng.value
  mapPickerVisible.value = false
}

function clearBurialLocation() {
  form.value.burialLat = null
  form.value.burialLng = null
}

function submit() {
  if (!form.value.name.trim()) return
  emit('submit', { ...form.value, photoFile: selectedPhotoFile.value })
}
</script>

<style scoped>
.member-form-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.member-form-intro {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(250, 246, 238, 0.88);
  border: 1px solid rgba(190, 162, 127, 0.22);
}

.member-form-intro strong {
  color: #6a4726;
}

.member-form-intro p {
  margin: 6px 0 0;
  color: #7d644b;
  line-height: 1.6;
}

.member-form {
  max-height: 68vh;
  overflow-y: auto;
  padding-right: 8px;
}

.member-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.member-form :deep(.el-divider__text) {
  color: var(--el-color-primary);
  font-weight: 700;
}

.field-group-tip {
  margin: -4px 0 14px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.field-group-tip--warning {
  color: var(--el-color-warning-dark-2);
}

.photo-form-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  margin-bottom: 14px;
  border-radius: 16px;
  border: 1px solid rgba(190, 162, 127, 0.24);
  background: linear-gradient(135deg, rgba(255,255,255,0.82), rgba(250,246,238,0.72));
}

.photo-form-preview {
  width: 82px;
  height: 82px;
  flex: 0 0 82px;
  border-radius: 18px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 30px;
  font-weight: 800;
  background: linear-gradient(135deg, #7f9dbd, #415d7a);
  box-shadow: 0 10px 24px rgba(91, 62, 32, 0.16);
}

.photo-form-preview.female {
  background: linear-gradient(135deg, #d99aaa, #a94f65);
}

.photo-form-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.photo-form-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
}

.photo-form-actions strong {
  width: 100%;
  color: #6a4726;
}

.photo-form-actions p {
  width: 100%;
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.source-spec-tip {
  margin-top: 6px;
}

.map-coordinate-tip {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.map-picker-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
}

.map-picker-tip {
  margin: 10px 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.map-picker-canvas {
  width: 100%;
  height: 440px;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(190, 162, 127, 0.28);
  background: #f5efe4;
}

.map-picker-result {
  margin-top: 10px;
  color: var(--el-text-color-regular);
  display: flex;
  flex-direction: column;
  gap: 4px;
  line-height: 1.5;
}

</style>
