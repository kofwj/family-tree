<template>
  <el-card class="settings-card" shadow="never">
    <template #header>
      <div class="settings-header">
        <div>
          <strong>治理域一：基础设置</strong>
          <p>修改族谱在首页、登录页、工作台侧栏和总览里的展示名称。</p>
        </div>
        <el-tag type="success">可即时生效</el-tag>
      </div>
    </template>

    <el-alert
      class="settings-scope-alert"
      type="info"
      :closable="false"
      show-icon
      title="这些是全站公开展示项"
    >
      <template #default>
        <div class="settings-scope-copy">
          <span>可修改角色：超级管理员、管理员。</span>
          <span>保存后，未登录首页、登录页以及所有已登录用户的工作台都会看到新的族谱名称和副标题。</span>
        </div>
      </template>
    </el-alert>

    <el-form label-position="top">
      <el-form-item label="族谱名称">
        <el-input v-model="draft.siteTitle" :disabled="readonly" maxlength="32" show-word-limit placeholder="例如：陈氏宗族家谱" />
      </el-form-item>
      <el-form-item label="族徽文字 / 姓氏">
        <el-input v-model="draft.familySurname" :disabled="readonly" maxlength="4" show-word-limit placeholder="例如：陈" />
      </el-form-item>
      <el-form-item label="副标题">
        <el-input v-model="draft.subtitle" :disabled="readonly" maxlength="48" show-word-limit placeholder="例如：承先祖之德 · 启后世之贤" />
      </el-form-item>
      <el-form-item label="首页英文标识">
        <el-input v-model="draft.coverKicker" :disabled="readonly" maxlength="48" show-word-limit placeholder="例如：CHEN CLAN · GENEALOGY" />
      </el-form-item>
      <el-form-item label="总览说明">
        <el-input v-model="draft.treeDescription" :disabled="readonly" maxlength="64" show-word-limit placeholder="例如：可阅读的大型关系结构 · 分层对齐 · 拖拽缩放" />
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
defineProps({
  draft: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
})
</script>
