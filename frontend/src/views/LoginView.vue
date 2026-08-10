<template>
  <div class="login-shell">
    <div class="login-ornament login-ornament-a"></div>
    <div class="login-ornament login-ornament-b"></div>
    <el-card class="login-card">
      <div class="login-hero">
        <div class="brand-kicker">CLAN · GENEALOGY</div>
        <h2>宗族家谱</h2>
        <p>{{ settings.subtitle }}</p>
        <p class="login-helper">登录后可查看家族世系、成员录与备份管理。</p>
      </div>
      <el-alert v-if="err" :title="err" type="error" :closable="false" style="margin-bottom: 12px" />
      <el-form label-position="top" @submit.prevent="login">
        <el-form-item label="账号">
          <el-input v-model="form.username" placeholder="请输入账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>

        <el-checkbox v-model="rememberMe" style="margin-bottom: 12px;">记住我（30天内免重复登录）</el-checkbox>

        <el-button type="primary" :loading="loading" style="width:100%" @click="login">登录</el-button>

        <div style="margin-top: 12px; font-size: 12px; color: #666; text-align: center; line-height: 1.6;">
          没有账号？请联系家族管理员获取账号和密码<br>
          忘记密码请联系管理员重置
        </div>
      </el-form>
    
      <div style="margin-top: 20px; text-align: center; font-size: 12px;">
        <el-link type="primary" @click="showForgot = true" style="font-size:12px">忘记密码？</el-link>
        &nbsp;&nbsp;
        <el-link type="success" @click="showRegister = true" style="font-size:12px">有邀请码？自助注册</el-link>
      </div>

      <!-- 忘记密码弹窗 -->
      <el-dialog v-model="showForgot" title="忘记密码" width="360px">
        <el-form>
          <el-form-item label="用户名或联系方式（邮箱/手机号）">
            <el-input v-model="forgotInput" placeholder="输入用户名 或 已绑定的邮箱/电话" />
          </el-form-item>
          <div style="color:#888;font-size:12px;">提交后会生成重置码，请联系管理员获取重置码使用。</div>
        </el-form>
        <template #footer>
          <el-button @click="showForgot=false">取消</el-button>
          <el-button type="primary" @click="doForgot">获取重置码</el-button>
        </template>
      </el-dialog>

      <!-- 邀请码注册弹窗 -->
      <el-dialog v-model="showRegister" title="使用邀请码注册" width="380px">
        <el-form>
          <el-form-item label="邀请码">
            <el-input v-model="regInvite" placeholder="管理员提供的邀请码" />
          </el-form-item>
          <el-form-item label="用户名">
            <el-input v-model="regUser" placeholder="登录用的账号名" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="regPass" type="password" show-password placeholder="符合规则的密码" />
          </el-form-item>
          <el-form-item label="显示名称（可选）">
            <el-input v-model="regDisplay" placeholder="家族中怎么称呼你" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showRegister=false">取消</el-button>
          <el-button type="success" @click="doRegister">注册</el-button>
        </template>
      </el-dialog>

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
  subtitle: '承先祖之德 · 启后世之贤',
})
const rememberMe = ref(false)

onMounted(async () => {
  try {
    const { data } = await api.get('/public-settings')
    if (data?.subtitle) {
      settings.value.subtitle = data.subtitle
    }
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
    if (rememberMe.value) {
      fd.append('remember_me', 'true')
    }
    const { data } = await api.post('/auth/login', fd)
    localStorage.setItem('isAuthenticated', 'true')
    router.push('/workspace')
  } catch (e) {
    err.value = e?.response?.data?.detail || '登录失败，请检查账号密码'
  } finally {
    loading.value = false
  }
}

const wechatLoading = ref(false)

async function wechatLogin() {
  wechatLoading.value = true
  err.value = ''
  try {
    const { data } = await api.get('/auth/wechat/qr-url')
    if (data?.qr_url) {
      // 直接跳转到微信授权页（扫码后会回调后端并设置 cookie）
      window.location.href = data.qr_url
    } else {
      err.value = '获取微信登录地址失败'
    }
  } catch (e) {
    err.value = e?.response?.data?.detail || '微信登录暂时不可用'
  } finally {
    wechatLoading.value = false
  }
}
</script>
