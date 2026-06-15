<template>
  <div class="home-cover">
    <div class="cover-glow cover-glow-a"></div>
    <div class="cover-glow cover-glow-b"></div>
    <div class="cover-inner">
      <div class="brand-kicker">CLAN · GENEALOGY</div>
      <h1>宗族家谱</h1>
      <p class="cover-subtitle" v-if="settings.subtitle">{{ settings.subtitle }}</p>
      
      <!-- Display the family tree general description / overview blurb -->
      <div class="cover-desc" v-if="settings.treeDescription">
        {{ settings.treeDescription }}
      </div>

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
  siteTitle: '宗族家谱',
  familySurname: '',
  subtitle: '承先祖之德 · 启后世之贤',
  coverKicker: 'CLAN · GENEALOGY',
  treeDescription: '',
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
