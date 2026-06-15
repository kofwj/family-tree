<template>
  <div class="login-shell">
    <div class="login-ornament login-ornament-a"></div>
    <div class="login-ornament login-ornament-b"></div>
    <el-card class="login-card">
      <div class="login-hero">
        <div class="brand-kicker">{{ settings.coverKicker }}</div>
        <h2>{{ settings.siteTitle }}</h2>
        <p>{{ settings.subtitle }}</p>
        <p class="login-helper">登录后可查看家族世系、成员录与备份管理。</p>
      </div>
      <el-alert v-if="err" :title="err" type="error" :closable="false" style="margin-bottom: 12px" />
      <el-form label-position="top" @submit.prevent="login">
        <el-form-item label="账号">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" style="width:100%" @click="login">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/client'

const router = useRouter()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const err = ref('')
const settings = ref({
  siteTitle: '陈氏宗族家谱',
  subtitle: '承先祖之德 · 启后世之贤',
  coverKicker: 'CHEN CLAN · GENEALOGY',
})

onMounted(async () => {
  try {
    const { data } = await api.get('/public-settings')
    settings.value = { ...settings.value, ...(data || {}) }
  } catch {
    // ignore public settings failure and keep defaults
  }
})

async function login() {
  loading.value = true
  err.value = ''
  try {
    const fd = new URLSearchParams()
    fd.append('username', form.value.username)
    fd.append('password', form.value.password)
    const { data } = await api.post('/auth/login', fd)
    localStorage.setItem('token', data.access_token)
    router.push('/workspace')
  } catch (e) {
    err.value = e?.response?.data?.detail || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}
</script>
