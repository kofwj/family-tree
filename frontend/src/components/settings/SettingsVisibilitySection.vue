<template>
  <el-card class="settings-card" shadow="never">
    <template #header>
      <div class="settings-header">
        <div>
          <strong>治理域二：显示策略</strong>
          <p>控制不同角色在成员录中可见字段范围的上限。</p>
        </div>
        <el-tag type="warning">字段分级治理</el-tag>
      </div>
    </template>

    <el-form label-position="top">
      <el-form-item label="只读成员字段模板">
        <el-radio-group
          v-model="draft.fieldVisibilityTemplates.viewer"
          :disabled="readonly"
          class="field-template-radio-group"
          data-testid="viewer-template-select"
        >
          <el-radio-button label="public">公开（最少字段）</el-radio-button>
          <el-radio-button label="archive">档案（中等字段）</el-radio-button>
          <el-radio-button label="sensitive">敏感（较全字段）</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="编辑者字段模板">
        <el-radio-group
          v-model="draft.fieldVisibilityTemplates.editor"
          :disabled="readonly"
          class="field-template-radio-group"
          data-testid="editor-template-select"
        >
          <el-radio-button label="public">公开（最少字段）</el-radio-button>
          <el-radio-button label="archive">档案（中等字段）</el-radio-button>
          <el-radio-button label="sensitive">敏感（较全字段）</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item>
        <div class="field-template-hint">
          模板仅控制字段可见范围上限；最终结果还会与“显示字段”配置取交集。
        </div>
      </el-form-item>
      <el-form-item v-if="editorTemplateLowerThanViewer">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="当前配置中，编辑者模板低于只读成员模板。"
          description="通常建议编辑者模板不低于只读成员模板。"
        />
      </el-form-item>
      <el-form-item>
        <div v-if="editorTemplateLowerThanViewer" class="field-template-warning-text">
          当前配置中，编辑者模板低于只读成员模板。通常建议编辑者模板不低于只读成员模板。
        </div>
      </el-form-item>

      <div class="settings-actions">
        <el-button @click="$emit('reset')">重置</el-button>
        <el-button type="primary" :disabled="readonly" :loading="saving" @click="$emit('save')">保存设置</el-button>
      </div>
    </el-form>
  </el-card>
</template>

<script setup>
defineProps({
  draft: { type: Object, required: true },
  readonly: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  editorTemplateLowerThanViewer: { type: Boolean, default: false },
})

defineEmits(['reset', 'save'])
</script>

<style scoped>
.field-template-radio-group {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
}

.field-template-radio-group :deep(.el-radio-button),
.field-template-radio-group :deep(.el-radio-button__inner) {
  white-space: normal;
}

.field-template-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.field-template-warning-text {
  color: var(--el-color-warning);
  font-size: 13px;
  line-height: 1.7;
}
</style>
