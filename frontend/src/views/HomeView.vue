<template>
  <div class="home-cover">
    <div class="cover-glow cover-glow-a"></div>
    <div class="cover-glow cover-glow-b"></div>
    <div class="cover-inner">
      <div class="brand-kicker">{{ effectiveCoverKicker }}</div>
      <h1>{{ settings.siteTitle }}</h1>
      <p class="cover-subtitle">{{ settings.subtitle }}</p>

      <div class="cover-pills">
        <span>宗族总览</span>
        <span>世系浏览</span>
        <span>成员检索</span>
      </div>

      <div v-if="isAuthenticated" class="cover-stats">
        <div class="cover-stat"><span>家族人数</span><strong>{{ stats.members }}</strong></div>
        <div class="cover-stat"><span>世代数</span><strong>{{ stats.generations }}</strong></div>
        <div class="cover-stat"><span>分支数</span><strong>{{ stats.roots }}</strong></div>
      </div>
      <p v-else class="cover-guest-note">登录后可查看完整家族世系、成员档案与资料治理工具。</p>

      <div class="cover-actions">
        <el-button v-if="isAuthenticated" type="primary" class="full-btn" @click="goWorkspace">进入家谱</el-button>
        <el-button v-if="isAuthenticated" plain class="full-btn" @click="goLogin">切换账号</el-button>
        <el-button v-else type="primary" class="full-btn" @click="goLogin">登录查看家谱</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()
const isAuthenticated = ref(false)
const stats = ref({ members: '--', generations: '--', roots: '--' })
const settings = ref({
  siteTitle: '陈氏宗族家谱',
  familySurname: '陈',
  subtitle: '承先祖之德 · 启后世之贤',
  coverKicker: 'CHEN CLAN · GENEALOGY',
})

const effectiveCoverKicker = computed(() => {
  const rawKicker = settings.value.coverKicker || ''
  if (rawKicker && rawKicker !== 'CHEN CLAN · GENEALOGY') {
    return rawKicker
  }
  const surname = settings.value.familySurname || '陈'
  const pinyinMap = {
    '陈': 'CHEN', '王': 'WANG', '张': 'ZHANG', '李': 'LI', '刘': 'LIU',
    '赵': 'ZHAO', '周': 'ZHOU', '吴': 'WU', '徐': 'XU', '孙': 'SUN',
    '胡': 'HU', '朱': 'ZHU', '高': 'GAO', '林': 'LIN', '何': 'HE',
    '郭': 'GUO', '马': 'MA', '罗': 'LUO', '梁': 'LIANG', '宋': 'SONG',
    '郑': 'ZHENG', '谢': 'XIE', '韩': 'HAN', '唐': 'TANG', '冯': 'FENG',
    '于': 'YU', '董': 'DONG', '萧': 'XIAO', '程': 'CHENG', '曹': 'CAO',
    '袁': 'YUAN', '邓': 'DENG', '许': 'XU', '傅': 'FU', '沈': 'SHEN',
    '曾': 'ZENG', '彭': 'PENG', '吕': 'LV', '苏': 'SU', '卢': 'LU',
    '蒋': 'JIANG', '蔡': 'CAI', '贾': 'JIA', '丁': 'DING', '魏': 'WEI',
    '薛': 'XUE', '叶': 'YE', '阎': 'YAN', '余': 'YU', '潘': 'PAN',
    '杜': 'DU', '戴': 'DAI', '夏': 'XIA', '钟': 'ZHONG', '汪': 'WANG',
    '田': 'TIAN', '任': 'REN', '姜': 'JIANG', '方': 'FANG', '范': 'FAN',
    '石': 'SHI', '廖': 'LIAO', '金': 'JIN', '邹': 'ZOU', '陆': 'LU',
    '郝': 'HAO', '孔': 'KONG', '白': 'BAI', '崔': 'CUI', '康': 'KANG',
    '毛': 'MAO', '邱': 'QIU', '秦': 'QIN', '江': 'JIANG', '史': 'SHI',
    '顾': 'GU', '侯': 'HOU', '邵': 'SHAO', '孟': 'MENG', '龙': 'LONG',
    '万': 'WAN', '段': 'DUAN', '雷': 'LEI', '钱': 'QIAN', '汤': 'TANG',
    '尹': 'YIN', '黎': 'LI', '易': 'YI', '常': 'CHANG', '武': 'WU',
    '乔': 'QIAO', '贺': 'HE', '赖': 'LAI', '龚': 'GONG', '文': 'WEN'
  }
  const eng = pinyinMap[surname] || surname.toUpperCase()
  return `${eng} CLAN · GENEALOGY`
})

function goWorkspace() {
  router.push('/workspace')
}
function goLogin() {
  localStorage.removeItem('token')
  router.push('/login')
}

onMounted(async () => {
  isAuthenticated.value = !!localStorage.getItem('token')

  try {
    const { data } = await api.get('/public-settings')
    settings.value = { ...settings.value, ...(data || {}) }
  } catch {
    // ignore public settings failure and keep defaults
  }

  if (!isAuthenticated.value) return

  try {
    const [m, t] = await Promise.all([api.get('/members'), api.get('/tree')])
    const members = m.data || []
    const roots = t.data || []
    const generations = new Set(members.map(x => x.generation).filter(Boolean)).size
    stats.value = { members: members.length, generations, roots: roots.length }
  } catch {
    // ignore
  }
})
</script>
