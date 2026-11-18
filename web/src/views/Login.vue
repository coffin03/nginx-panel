<template>
  <div class="login-wrap">
    <ThemeSwitch class="theme-float" />
    <div class="login-shell">
      <aside class="login-aside">
        <div class="aside-brand">
          <img class="aside-logo" src="/favicon.svg" alt="logo" />
          <span>nginx<em>-panel</em></span>
        </div>
        <h2 class="aside-title">把 nginx 配置<br />变成看得懂、敢改的界面</h2>
        <ul class="features">
          <li>
            <el-icon><EditPen /></el-icon>
            <span>结构化表单与代码编辑双模式</span>
          </li>
          <li>
            <el-icon><CircleCheck /></el-icon>
            <span>保存即校验，失败自动还原</span>
          </li>
          <li>
            <el-icon><Clock /></el-icon>
            <span>每次改动留快照，随时回滚</span>
          </li>
          <li>
            <el-icon><Lock /></el-icon>
            <span>纯本地运行，数据不出本机</span>
          </li>
        </ul>
        <div class="aside-foot">127.0.0.1 · 本地管理台</div>
      </aside>

      <section class="login-main">
        <h1 class="login-title">{{ auth.initialized ? '欢迎回来' : '初始化面板' }}</h1>
        <p class="login-sub muted">
          {{ auth.initialized ? '登录后管理本机 nginx 配置与进程' : '首次使用，请创建管理员账号' }}
        </p>
        <el-form :model="form" label-position="top" @submit.prevent="submit">
          <el-form-item label="用户名">
            <el-input v-model="form.username" size="large" autocomplete="username" placeholder="admin" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="form.password"
              size="large"
              type="password"
              show-password
              autocomplete="current-password"
              placeholder="至少 6 位"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-form-item v-if="!auth.initialized" label="确认密码">
            <el-input
              v-model="form.confirm"
              size="large"
              type="password"
              show-password
              placeholder="再次输入密码"
              @keyup.enter="submit"
            />
          </el-form-item>
          <el-button type="primary" size="large" class="submit" :loading="loading" @click="submit">
            {{ auth.initialized ? '登录' : '创建并进入' }}
          </el-button>
        </el-form>
        <p class="hint muted">数据全部保存在本机 SQLite，不联网、不上传。</p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, Clock, EditPen, Lock } from '@element-plus/icons-vue'
import ThemeSwitch from '../components/ThemeSwitch.vue'
import { apiPost } from '../api'
import { auth, refreshAuth } from '../store'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: '', confirm: '' })

async function submit() {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  if (!auth.initialized && form.password !== form.confirm) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  loading.value = true
  const isSetup = !auth.initialized
  try {
    const path = isSetup ? '/auth/setup' : '/auth/login'
    await apiPost(path, { username: form.username.trim(), password: form.password })
    await refreshAuth()
    ElMessage.success(isSetup ? '管理员已创建' : '登录成功')
    router.push('/')
  } catch (e) {
    /* 错误已提示 */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  position: relative;
}
.theme-float {
  position: absolute;
  top: 22px;
  right: 24px;
}
.login-shell {
  display: flex;
  width: min(880px, 100%);
  border-radius: 20px;
  overflow: hidden;
  background: var(--ngp-surface);
  border: 1px solid var(--ngp-border);
  box-shadow: var(--ngp-shadow-lg);
}
.login-aside {
  width: 44%;
  min-width: 320px;
  padding: 38px 34px 30px;
  color: #eafaf4;
  background: linear-gradient(155deg, #12866a 0%, #0d6a53 45%, #08402f 100%);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}
.login-aside::after {
  content: '';
  position: absolute;
  width: 320px;
  height: 320px;
  right: -120px;
  bottom: -140px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(52, 211, 153, 0.45), transparent 68%);
  pointer-events: none;
}
.aside-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 19px;
  font-weight: 700;
  letter-spacing: 0.2px;
}
.aside-brand em {
  font-style: normal;
  color: #9df3cf;
}
.aside-logo {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: block;
  box-shadow: 0 10px 24px -12px rgba(0, 0, 0, 0.6);
}
.aside-title {
  margin: 34px 0 24px;
  font-size: 22px;
  line-height: 1.5;
  font-weight: 650;
  letter-spacing: 0.2px;
}
.features {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 13px;
  font-size: 13px;
  color: rgba(234, 250, 244, 0.88);
  position: relative;
  z-index: 1;
}
.features li {
  display: flex;
  align-items: center;
  gap: 9px;
}
.features .el-icon {
  color: #9df3cf;
  font-size: 15px;
}
.aside-foot {
  margin-top: auto;
  padding-top: 26px;
  font-size: 11.5px;
  letter-spacing: 0.6px;
  color: rgba(234, 250, 244, 0.55);
}
.login-main {
  flex: 1;
  padding: 42px 44px 32px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.login-title {
  margin: 0;
  font-size: 23px;
  font-weight: 650;
  letter-spacing: -0.2px;
}
.login-sub {
  margin: 7px 0 24px;
  font-size: 13px;
}
.submit {
  width: 100%;
  margin-top: 6px;
}
.hint {
  margin: 22px 0 0;
  font-size: 12px;
  text-align: center;
}
@media (max-width: 780px) {
  .login-aside {
    display: none;
  }
  .login-main {
    padding: 34px 26px 26px;
  }
}
</style>