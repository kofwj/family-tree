<template>
  <div class="home-cover">
    <div class="cover-glow cover-glow-a"></div>
    <div class="cover-glow cover-glow-b"></div>
    <div class="cover-inner">
      <div class="brand-kicker">{{ settings.coverKicker }}</div>
      <h1>{{ settings.siteTitle }}</h1>
      <p class="cover-subtitle">{{ settings.subtitle }}</p>

      <div class="cover-pills">
        <span>宗族总览</span>
        <span>世系浏览</span>
        <span>成员检索</span>
      </div>

      <div class="cover-stats">
        <div class="cover-stat"><span>家族人数</span><strong>{{ stats.members }}</strong></div>
        <div class="cover-stat"><span>世代数</span><strong>{{ stats.generations }}</strong></div>
        <div class="cover-stat"><span>分支数</span><strong>{{ stats.roots }}</strong></div>
      </div>

      <div class="cover-actions">
        <el-button type="primary" class="full-btn" @click="goWorkspace">进入家谱</el-button>
        <el-button plain class="full-btn" @click="goLogin">切换账号</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()
const stats = ref({ members: '--', generations: '--', roots: '--' })
const settings = ref({
  siteTitle: '陈氏宗族家谱',
  familySurname: '陈',
  subtitle: '承先祖之德 · 启后世之贤',
  coverKicker: 'CHEN CLAN · GENEALOGY',
})

function goWorkspace() {
  router.push('/workspace')
}
function goLogin() {
  localStorage.removeItem('token')
  router.push('/login')
}

onMounted(async () => {
  try {
    const { data } = await api.get('/public-settings')
    settings.value = { ...settings.value, ...(data || {}) }
  } catch {
    // ignore public settings failure and keep defaults
  }

  if (!localStorage.getItem('token')) return

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
