<template>
  <div class="settings-page governance-workbench">
    <section class="governance-hero settings-card">
      <div class="governance-hero__main">
        <div class="governance-hero__copy">
          <p class="governance-hero__eyebrow">GOVERNANCE WORKBENCH</p>
          <h2>系统治理工作台</h2>
          <p>优先处理审核、数据质量、来源可信度和审计风险；低频的基础配置收纳到后置分区，避免所有设置堆在同一个长页面。</p>
        </div>
        <div class="governance-hero__actions">
          <el-button v-if="canViewQuality" @click="emit('refresh-quality')">重新检查质量</el-button>
          <el-button v-if="canExportGedcom" @click="emit('export-gedcom')">导出 GEDCOM</el-button>
          <el-button v-if="canManageSources" type="primary" @click="openSourceDialog()">新增来源</el-button>
        </div>
      </div>
    </section>

    <section class="governance-kpi-grid" aria-label="治理总览指标">
      <button class="governance-kpi-card is-warning" type="button" @click="jumpTab(canShowReview ? 'review' : 'overview')">
        <span>待审核结构变更</span>
        <strong>{{ pendingReviewRequests.length }}</strong>
        <small>{{ canShowReview ? '父母、配偶、世代等核心关系变更' : '当前角色无审核台权限' }}</small>
      </button>
      <button class="governance-kpi-card is-danger" type="button" @click="jumpTab(canViewQuality ? 'quality' : 'overview')">
        <span>数据质量问题</span>
        <strong>{{ qualityTotal }}</strong>
        <small>错误 {{ qualitySeverity('error') }} · 警告 {{ qualitySeverity('warning') }} · 提示 {{ qualitySeverity('info') }}</small>
      </button>
      <button class="governance-kpi-card is-source" type="button" @click="jumpTab(canShowSources ? 'sources' : 'overview')">
        <span>来源库记录</span>
        <strong>{{ sourceCount }}</strong>
        <small>纸谱、口述、墓碑、户籍等来源归档</small>
      </button>
      <button class="governance-kpi-card is-audit" type="button" @click="jumpTab(canShowAudit ? 'audit' : 'overview')">
        <span>近期审计</span>
        <strong>{{ auditLogs.length }}</strong>
        <small>高敏 {{ highPriorityAuditCount }} · 成员类 {{ memberAuditCount }}</small>
      </button>
    </section>

    <el-tabs v-model="activeGovernanceTab" class="governance-tabs" type="border-card">
      <el-tab-pane name="overview">
        <template #label>治理总览</template>
        <div class="overview-grid">
          <el-card class="settings-card overview-card" shadow="never">
            <template #header>
              <div class="section-card-header">
                <strong>优先处理事项</strong>
                <el-tag type="warning" effect="plain">按风险排序</el-tag>
              </div>
            </template>

            <div class="task-list">
              <button v-if="canShowReview && pendingReviewRequests.length" class="task-item is-warning" type="button" @click="jumpTab('review')">
                <b>{{ pendingReviewRequests.length }} 条结构变更待审核</b>
                <span>涉及父母、配偶、世代、支系等核心关系，建议优先处理。</span>
              </button>
              <button v-if="canViewQuality && qualitySeverity('error')" class="task-item is-danger" type="button" @click="jumpTab('quality')">
                <b>{{ qualitySeverity('error') }} 个严重数据质量问题</b>
                <span>存在无效关系、世代异常等可能影响族谱结构的问题。</span>
              </button>
              <button v-if="canViewQuality && qualitySeverity('warning')" class="task-item" type="button" @click="jumpTab('quality')">
                <b>{{ qualitySeverity('warning') }} 个质量警告</b>
                <span>建议逐步处理配偶单向、缺少父母、隐私复核等问题。</span>
              </button>
              <button v-if="canShowSources && !sourceCount" class="task-item" type="button" @click="jumpTab('sources')">
                <b>来源库尚未建立</b>
                <span>建议先录入纸谱、口述、墓碑、户籍等核心来源，后续给成员字段添加引用。</span>
              </button>
              <div v-if="!hasPriorityTasks" class="empty-governance-state">
                <b>暂无高优先级待办</b>
                <span>可以继续补充来源、检查质量或查看近期审计。</span>
              </div>
            </div>
          </el-card>

          <el-card class="settings-card overview-card" shadow="never">
            <template #header><strong>治理速览</strong></template>
            <div class="governance-notes">
              <div class="governance-note-item">
                <b>当前角色</b>
                <span>{{ currentUser?.displayName || '未登录' }} / {{ roleLabel(currentUser?.role) }}</span>
              </div>
              <div class="governance-note-item">
                <b>显示策略</b>
                <span>{{ visibilitySummary }}</span>
              </div>
              <div class="governance-note-item">
                <b>账号状态</b>
                <span>启用 {{ activeUserCount }} 个，停用 {{ disabledUserCount }} 个</span>
              </div>
              <div class="governance-note-item">
                <b>族谱配置</b>
                <span>{{ draft.siteTitle || '未命名族谱' }} · {{ draft.familySurname || '未设置姓氏' }}</span>
              </div>
            </div>
          </el-card>

          <el-card v-if="canViewQuality" class="settings-card overview-card" shadow="never">
            <template #header>
              <div class="section-card-header">
                <strong>质量问题预览</strong>
                <el-button link type="primary" @click="jumpTab('quality')">查看全部</el-button>
              </div>
            </template>
            <div v-if="qualityIssues.length" class="compact-issue-list">
              <article v-for="issue in qualityIssues.slice(0, 5)" :key="`${issue.category}-${issue.memberId}-${issue.message}`" class="compact-issue-item">
                <el-tag :type="qualityTagType(issue.severity)" size="small">{{ qualitySeverityLabel(issue.severity) }}</el-tag>
                <div>
                  <b>{{ issue.memberName || (issue.memberId ? `#${issue.memberId}` : '全局') }}</b>
                  <span>{{ issue.message }}</span>
                </div>
              </article>
            </div>
            <el-empty v-else description="暂无质量问题" />
          </el-card>

          <el-card class="settings-card permission-guide-card" shadow="never">
            <el-collapse v-model="permissionGuideOpen" class="permission-guide-collapse">
              <el-collapse-item name="guide">
                <template #title>
                  <div class="permission-guide-title">
                    <strong>权限治理说明</strong>
                    <span>点击展开角色职责</span>
                  </div>
                </template>
                <div class="future-list compact">
                  <div><b>超级管理员</b><span>拥有用户、备份、设置和成员维护全部权限。</span></div>
                  <div><b>管理员</b><span>可维护成员、备份和基础展示设置，但不能管理用户。</span></div>
                  <div><b>编辑者</b><span>可新增成员并编辑成员基础资料；核心结构变更需提交审核。</span></div>
                  <div><b>只读成员</b><span>仅可查看授权范围内的家谱树和成员录。</span></div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="canViewQuality" name="quality">
        <template #label>数据质量（{{ qualityTotal }}）</template>
        <el-card class="settings-card" shadow="never">
          <template #header>
            <div class="section-card-header">
              <div>
                <strong>数据质量中心</strong>
                <p>集中发现结构、来源、隐私与档案完整度问题。</p>
              </div>
              <el-button size="small" @click="emit('refresh-quality')">重新检查</el-button>
            </div>
          </template>
          <div class="quality-summary">
            <el-tag type="danger">错误 {{ qualitySeverity('error') }}</el-tag>
            <el-tag type="warning">警告 {{ qualitySeverity('warning') }}</el-tag>
            <el-tag type="info">提示 {{ qualitySeverity('info') }}</el-tag>
            <el-tag>总计 {{ qualityTotal }}</el-tag>
          </div>
          <el-table :data="qualityIssues" max-height="520" empty-text="暂无质量问题">
            <el-table-column label="级别" width="90">
              <template #default="{ row }"><el-tag :type="qualityTagType(row.severity)" size="small">{{ qualitySeverityLabel(row.severity) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="category" label="类别" width="150" show-overflow-tooltip />
            <el-table-column label="成员" width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.memberName || (row.memberId ? `#${row.memberId}` : '全局') }}</template>
            </el-table-column>
            <el-table-column prop="message" label="问题说明" min-width="280" show-overflow-tooltip />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane v-if="canShowReview" name="review">
        <template #label>结构审核（{{ pendingReviewRequests.length }}）</template>
        <el-card class="settings-card" shadow="never">
          <template #header>
            <div class="section-card-header">
              <div>
                <strong>结构变更审核流</strong>
                <p>核心关系变更先入队审核，避免误改父母、配偶、世代和支系。</p>
              </div>
              <el-tag type="warning">待审核 {{ pendingReviewRequests.length }}</el-tag>
            </div>
          </template>
          <el-table :data="reviewRequests" max-height="520" empty-text="暂无审核请求">
            <el-table-column label="状态" width="96">
              <template #default="{ row }"><el-tag :type="reviewTagType(row.status)" size="small">{{ reviewStatusLabel(row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="成员" width="150" show-overflow-tooltip>
              <template #default="{ row }">{{ row.targetLabel || `#${row.memberId}` }}</template>
            </el-table-column>
            <el-table-column label="提交人" width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.actorUsername || '-' }}</template>
            </el-table-column>
            <el-table-column label="变更摘要" min-width="280" show-overflow-tooltip>
              <template #default="{ row }">{{ reviewDiffText(row) }}</template>
            </el-table-column>
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
            </el-table-column>
            <el-table-column v-if="canApproveReview" label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === 'pending'" link type="primary" size="small" @click="emit('approve-review', row)">通过</el-button>
                <el-button v-if="row.status === 'pending'" link type="danger" size="small" @click="rejectReview(row)">驳回</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane v-if="canShowSources" name="sources">
        <template #label>来源与 GEDCOM（{{ sourceCount }}）</template>
        <el-card class="settings-card" shadow="never">
          <template #header>
            <div class="section-card-header">
              <div>
                <strong>来源库与 GEDCOM</strong>
                <p>把纸谱、口述、墓碑、户籍等来源统一归档，并用于成员字段引用。</p>
              </div>
              <div class="section-actions">
                <el-button v-if="canExportGedcom" size="small" @click="emit('export-gedcom')">导出 GEDCOM</el-button>
                <el-button v-if="canManageSources" type="primary" size="small" @click="openSourceDialog()">新增来源</el-button>
              </div>
            </div>
          </template>
          <div class="source-guidance">
            <b>建议来源类型：</b>纸谱、口述、墓碑、户籍、讣告、访谈、微信记录。成员详情中可把来源绑定到“出生、父母关系、配偶关系、传略”等字段。
          </div>
          <el-table :data="sources" max-height="520" empty-text="暂无来源记录">
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
            <el-table-column prop="sourceType" label="类型" width="110" show-overflow-tooltip />
            <el-table-column prop="author" label="作者/提供人" width="150" show-overflow-tooltip />
            <el-table-column prop="repository" label="馆藏/保存处" width="160" show-overflow-tooltip />
            <el-table-column prop="reference" label="编号/页码" width="150" show-overflow-tooltip />
            <el-table-column v-if="canManageSources" label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openSourceDialog(row)">编辑</el-button>
                <el-button link type="danger" size="small" @click="emit('delete-source', row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane v-if="canViewUsers" name="users">
        <template #label>用户权限（{{ users.length }}）</template>
        <SettingsUsersSection
          :users="users"
          :user-loading="userLoading"
          :current-user="currentUser"
          :can-view-users="canViewUsers"
          :can-create-user="canCreateUser"
          :can-edit-user="canEditUser"
          :can-disable-user="canDisableUser"
          :can-reset-password="canResetPassword"
          :role-label="roleLabel"
          :format-time="formatTime"
          :member-name="memberName"
          :scope-hint="scopeHint"
          @open-user-dialog="openUserDialog()"
          @edit-user="openUserDialog"
          @reset-password="openPasswordDialog"
          @toggle-user-active="toggleUserActive"
        />
      </el-tab-pane>

      <el-tab-pane v-if="canManageFamilies" name="families">
        <template #label>家族管理</template>
        <el-card class="settings-card" shadow="never">
          <template #header>
            <div class="section-card-header">
              <strong>家族列表</strong>
              <el-button v-if="canEditFamilies" type="primary" size="small" @click="openFamilyDialog()">新增家族</el-button>
            </div>
          </template>
          
          <el-table :data="families" stripe border>
            <el-table-column prop="name" label="家族名称" min-width="140" />
            <el-table-column prop="surname" label="姓氏" width="100" align="center" />
            <el-table-column prop="siteTitle" label="站点标题" min-width="180" />
            <el-table-column label="主家族" width="100" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.isPrimary" type="success" size="small">主</el-tag>
                <span v-else>—</span>
              </template>
            </el-table-column>
            <el-table-column label="成员数" width="100" align="center">
              <template #default="{ row }">
                {{ row.memberCount || 0 }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" align="center" fixed="right">
              <template #default="{ row }">
                <el-button v-if="canEditFamilies" link type="primary" size="small" @click="openFamilyDialog(row)">编辑</el-button>
                <el-button v-if="canEditFamilies" link type="info" size="small" @click="manageFamilyUsers(row)">权限</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- Family Edit Dialog -->
        <el-dialog v-model="familyDialogVisible" :title="editingFamily ? '编辑家族' : '新增家族'" width="600px">
          <el-form :model="familyForm" label-width="100px">
            <el-form-item label="家族名称">
              <el-input v-model="familyForm.name" placeholder="例如：陈氏宗族" />
            </el-form-item>
            <el-form-item label="姓氏">
              <el-input v-model="familyForm.surname" placeholder="例如：陈" maxlength="2" />
            </el-form-item>
            <el-form-item label="站点标题">
              <el-input v-model="familyForm.siteTitle" placeholder="例如：陈氏宗族家谱" />
            </el-form-item>
            <el-form-item label="副标题">
              <el-input v-model="familyForm.subtitle" placeholder="例如：承先祖之德 · 启后世之贤" />
            </el-form-item>
            <el-form-item label="英文标识">
              <el-input v-model="familyForm.coverKicker" placeholder="例如：CHEN CLAN · GENEALOGY" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="familyForm.description" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="familyDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="savingFamily" @click="saveFamily">保存</el-button>
          </template>
        </el-dialog>

        <!-- Family Users Dialog -->
        <el-dialog v-model="familyUsersDialogVisible" :title="`${currentFamilyForUsers?.name || ''} - 用户权限管理`" width="700px">
          <div style="margin-bottom: 16px">
            <el-button type="primary" size="small" @click="openAddFamilyUserDialog">添加用户</el-button>
          </div>
          <el-table :data="familyUsers" stripe border>
            <el-table-column prop="username" label="用户名" width="140" />
            <el-table-column prop="displayName" label="显示名称" min-width="120" />
            <el-table-column label="角色" width="120" align="center">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'editor' ? 'warning' : 'info'" size="small">
                  {{ row.role === 'admin' ? '管理员' : row.role === 'editor' ? '编辑者' : '查看者' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="removeFamilyUser(row)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-dialog>

        <!-- Add Family User Dialog -->
        <el-dialog v-model="addFamilyUserDialogVisible" title="添加用户到家族" width="500px">
          <el-form label-width="80px">
            <el-form-item label="选择用户">
              <el-select v-model="newFamilyUser.userId" placeholder="请选择用户" style="width: 100%">
                <el-option v-for="u in availableUsers" :key="u.id" :label="`${u.displayName} (${u.username})`" :value="u.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="角色">
              <el-select v-model="newFamilyUser.role" placeholder="请选择角色" style="width: 100%">
                <el-option label="查看者" value="viewer" />
                <el-option label="编辑者" value="editor" />
                <el-option label="管理员" value="admin" />
              </el-select>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="addFamilyUserDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="savingFamilyUser" @click="addFamilyUser">添加</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <el-tab-pane v-if="canShowSettings" name="settings">
        <template #label>基础与显示</template>
        <div class="settings-config-grid">
          <SettingsBasicSection :draft="draft" :readonly="readonly" />
          <SettingsVisibilitySection
            :draft="draft"
            :readonly="readonly"
            :saving="saving"
            :editor-template-lower-than-viewer="editorTemplateLowerThanViewer"
            @reset="resetDraft"
            @save="submit"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="canShowAudit" name="audit">
        <template #label>审计日志（{{ auditLogs.length }}）</template>
        <SettingsAuditSection
          :audit-logs="auditLogs"
          :high-priority-audit-count="highPriorityAuditCount"
          :member-audit-count="memberAuditCount"
          :format-time="formatTime"
          :audit-action-label="auditActionLabel"
          :audit-target-label="auditTargetLabel"
          :audit-priority-label="auditPriorityLabel"
          :audit-tag-type="auditTagType"
          :audit-detail-text="auditDetailText"
        />
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="userDialogVisible" :title="editingUser?.id ? '编辑用户' : '新增用户'" width="520px">
      <el-form label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="userDraft.username" :disabled="!!editingUser?.id" placeholder="例如：editor01" />
        </el-form-item>
        <el-form-item v-if="!editingUser?.id" label="初始密码">
          <el-input v-model="userDraft.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="userDraft.displayName" placeholder="例如：族谱编辑员" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userDraft.role" style="width: 100%" :disabled="editingUser?.username === 'admin'">
            <el-option v-for="r in roles" :key="r.role" :label="r.label" :value="r.role" />
          </el-select>
        </el-form-item>
        <el-form-item label="绑定成员">
          <el-select
            v-model="userDraft.memberId"
            clearable
            filterable
            style="width: 100%"
            placeholder="不绑定则仅管理员可正常使用全量权限"
          >
            <el-option v-for="member in memberOptions" :key="member.id" :label="memberOptionLabel(member)" :value="member.id" />
          </el-select>
          <div class="form-hint">{{ scopeHint(userDraft.role, userDraft.memberId) }}</div>
        </el-form-item>
        <el-form-item label="邮箱 / 手机">
          <div class="inline-fields">
            <el-input v-model="userDraft.email" placeholder="邮箱，可选" />
            <el-input v-model="userDraft.phone" placeholder="手机，可选" />
          </div>
        </el-form-item>
        <el-form-item label="账号状态">
          <el-switch v-model="userDraft.isActive" active-text="启用" inactive-text="停用" :disabled="editingUser?.id === currentUser?.id" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" title="重置密码" width="420px">
      <el-form label-position="top">
        <el-form-item label="用户">
          <el-input :model-value="passwordUser?.displayName || passwordUser?.username" disabled />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="newPassword" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="resetPassword">确认重置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sourceDialogVisible" :title="editingSource?.id ? '编辑来源' : '新增来源'" width="560px">
      <el-form label-position="top">
        <el-form-item label="来源标题"><el-input v-model="sourceDraft.title" placeholder="如：王氏宗谱 1998 版" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="12"><el-form-item label="来源类型"><el-input v-model="sourceDraft.source_type" placeholder="纸谱/口述/墓碑/户籍" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="作者/提供人"><el-input v-model="sourceDraft.author" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="馆藏/保存处"><el-input v-model="sourceDraft.repository" /></el-form-item>
        <el-form-item label="编号/页码/档号"><el-input v-model="sourceDraft.reference" /></el-form-item>
        <el-form-item label="链接"><el-input v-model="sourceDraft.url" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="sourceDraft.note" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveSource">保存来源</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { formatDateTimeCN } from '../utils/datetime'
import SettingsBasicSection from './settings/SettingsBasicSection.vue'
import SettingsVisibilitySection from './settings/SettingsVisibilitySection.vue'
import SettingsUsersSection from './settings/SettingsUsersSection.vue'
import SettingsAuditSection from './settings/SettingsAuditSection.vue'

const props = defineProps({
  settings: { type: Object, required: true },
  saving: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false },
  users: { type: Array, default: () => [] },
  roles: { type: Array, default: () => [] },
  members: { type: Array, default: () => [] },
  auditLogs: { type: Array, default: () => [] },
  qualityReport: { type: Object, default: () => ({ summary: { total: 0, bySeverity: {}, byCategory: {} }, issues: [] }) },
  reviewRequests: { type: Array, default: () => [] },
  sources: { type: Array, default: () => [] },
  families: { type: Array, default: () => [] },
  currentUser: { type: Object, default: null },
  userLoading: { type: Boolean, default: false },
  canViewUsers: { type: Boolean, default: false },
  canCreateUser: { type: Boolean, default: false },
  canEditUser: { type: Boolean, default: false },
  canDisableUser: { type: Boolean, default: false },
  canResetPassword: { type: Boolean, default: false },
  canViewSettings: { type: Boolean, default: false },
  canViewQuality: { type: Boolean, default: false },
  canViewReview: { type: Boolean, default: false },
  canApproveReview: { type: Boolean, default: false },
  canViewSources: { type: Boolean, default: false },
  canManageSources: { type: Boolean, default: false },
  canExportGedcom: { type: Boolean, default: false },
  canViewAudit: { type: Boolean, default: false },
  canManageFamilies: { type: Boolean, default: false },
  canEditFamilies: { type: Boolean, default: false },
})

const emit = defineEmits([
  'save-settings', 'create-user', 'update-user', 'toggle-user-active', 'reset-user-password',
  'refresh-quality', 'approve-review', 'reject-review',
  'create-source', 'update-source', 'delete-source', 'export-gedcom',
  'save-family', 'load-family-users', 'add-family-user', 'remove-family-user',
])

const draft = reactive({
  siteTitle: '',
  familySurname: '',
  subtitle: '',
  coverKicker: '',
  treeDescription: '',
  fieldVisibilityTemplates: { viewer: 'public', editor: 'archive' },
})
const userDialogVisible = ref(false)
const passwordDialogVisible = ref(false)
const permissionGuideOpen = ref([])
const editingUser = ref(null)
const passwordUser = ref(null)
const newPassword = ref('')
const sourceDialogVisible = ref(false)
const editingSource = ref(null)
const userDraft = reactive({ username: '', password: '', displayName: '', role: 'viewer', memberId: null, email: '', phone: '', isActive: true })
const sourceDraft = reactive({ title: '', source_type: '', author: '', repository: '', reference: '', url: '', note: '' })

// Family management
const familyDialogVisible = ref(false)
const familyUsersDialogVisible = ref(false)
const addFamilyUserDialogVisible = ref(false)
const editingFamily = ref(null)
const currentFamilyForUsers = ref(null)
const familyUsers = ref([])
const savingFamily = ref(false)
const savingFamilyUser = ref(false)
const familyForm = reactive({
  name: '',
  surname: '',
  siteTitle: '',
  subtitle: '',
  coverKicker: '',
  description: '',
})
const newFamilyUser = reactive({
  userId: null,
  role: 'viewer',
})

const availableUsers = computed(() => props.users.filter(u => u.isActive))

const activeGovernanceTab = ref('overview')
const memberOptions = computed(() => [...(props.members || [])].sort((a, b) => {
  const ga = Number(a?.generation || 0)
  const gb = Number(b?.generation || 0)
  if (ga !== gb) return ga - gb
  return String(a?.name || '').localeCompare(String(b?.name || ''), 'zh-Hans-CN')
}))

function resetDraft() {
  Object.assign(draft, {
    siteTitle: props.settings.siteTitle || '陈氏宗族家谱',
    familySurname: props.settings.familySurname || '陈',
    subtitle: props.settings.subtitle || '承先祖之德 · 启后世之贤',
    coverKicker: props.settings.coverKicker || 'CHEN CLAN · GENEALOGY',
    treeDescription: props.settings.treeDescription || '可阅读的大型关系结构 · 分层对齐 · 拖拽缩放',
    fieldVisibilityTemplates: {
      viewer: props.settings?.fieldVisibilityTemplates?.viewer || 'public',
      editor: props.settings?.fieldVisibilityTemplates?.editor || 'archive',
    },
  })
}

const TEMPLATE_RANK = { public: 1, archive: 2, sensitive: 3 }
const editorTemplateLowerThanViewer = computed(() => {
  const viewer = draft?.fieldVisibilityTemplates?.viewer || 'public'
  const editor = draft?.fieldVisibilityTemplates?.editor || 'archive'
  return (TEMPLATE_RANK[editor] || 0) < (TEMPLATE_RANK[viewer] || 0)
})

const highPriorityAuditCount = computed(() => (props.auditLogs || []).filter(row => row?.detail?.auditPriority === 'high').length)
const memberAuditCount = computed(() => (props.auditLogs || []).filter(row => String(row?.action || '').startsWith('member.')).length)
const activeUserCount = computed(() => (props.users || []).filter(user => user?.isActive !== false).length)
const disabledUserCount = computed(() => Math.max((props.users || []).length - activeUserCount.value, 0))
const visibilitySummary = computed(() => {
  const viewer = draft?.fieldVisibilityTemplates?.viewer || 'public'
  const editor = draft?.fieldVisibilityTemplates?.editor || 'archive'
  return `只读：${templateLabel(viewer)} / 编辑：${templateLabel(editor)}`
})
const qualityIssues = computed(() => props.qualityReport?.issues || [])
const qualityTotal = computed(() => props.qualityReport?.summary?.total || 0)
const pendingReviewRequests = computed(() => (props.reviewRequests || []).filter(row => row?.status === 'pending'))
const sourceCount = computed(() => (props.sources || []).length)
const canShowReview = computed(() => props.canViewReview || props.canApproveReview || (props.reviewRequests || []).length > 0)
const canShowSources = computed(() => props.canViewSources || props.canManageSources || props.canExportGedcom || sourceCount.value > 0)
const canShowAudit = computed(() => props.canViewAudit || (props.auditLogs || []).length > 0)
const canShowSettings = computed(() => props.canViewSettings || !props.readonly)
const hasPriorityTasks = computed(() => (
  (canShowReview.value && pendingReviewRequests.value.length > 0)
  || (props.canViewQuality && (qualitySeverity('error') > 0 || qualitySeverity('warning') > 0))
  || (canShowSources.value && sourceCount.value === 0)
))

function templateLabel(key) {
  return {
    public: '公开',
    archive: '档案',
    sensitive: '敏感',
  }[key] || key
}

function roleLabel(role) {
  return (props.roles || []).find(r => r.role === role)?.label || role || '未设置'
}

function formatTime(value) {
  return formatDateTimeCN(value)
}

function auditActionLabel(action) {
  return {
    'auth.login': '登录',
    'user.create': '创建用户',
    'user.update': '更新用户',
    'user.disable': '停用用户',
    'user.enable': '启用用户',
    'user.reset_password': '重置密码',
    'settings.update': '修改设置',
    'member.create': '新增成员',
    'member.update': '更新成员',
    'member.delete': '删除成员',
    'member.import_excel': '导入Excel',
    'member.import_default': '导入内置数据',
    'backup.create': '创建备份',
    'backup.delete': '删除备份',
    'backup.restore': '恢复备份',
    'review.create': '提交审核',
    'review.approve': '审核通过',
    'review.reject': '审核驳回',
    'source.create': '创建来源',
    'source.update': '更新来源',
    'source.delete': '删除来源',
    'source.cite': '添加引用',
  }[action] || action
}

function auditTargetLabel(row) {
  return row?.targetLabel || row?.targetId || '—'
}

function auditPriorityLabel(row) {
  const detail = row?.detail || {}
  if (detail?.auditPriority === 'high') return '高敏字段'
  if ((detail?.fieldCategories || {}).structure?.length) return '结构类变更'
  if ((detail?.fieldCategories || {}).archive?.length) return '档案类变更'
  if ((detail?.fieldCategories || {}).system?.length) return '系统类变更'
  return ''
}

function auditTagType(row) {
  const detail = row?.detail || {}
  if (detail?.auditPriority === 'high') return 'danger'
  if ((detail?.fieldCategories || {}).structure?.length) return 'warning'
  if ((detail?.fieldCategories || {}).system?.length) return 'primary'
  return 'info'
}

function auditDetailText(row) {
  const detail = row?.detail || {}
  if (detail?.changes && typeof detail.changes === 'object') {
    const entries = Object.entries(detail.changes)
    if (!entries.length) return '—'
    return entries.slice(0, 3).map(([key, value]) => {
      if (value && typeof value === 'object' && 'after' in value) return `${key}: ${Array.isArray(value.after) ? value.after.join('、') : value.after}`
      return `${key}: ${Array.isArray(value) ? value.join('、') : value}`
    }).join('；')
  }
  if (row?.detail && typeof row.detail === 'object') {
    return Object.entries(row.detail).slice(0, 3).map(([key, value]) => {
      if (value && typeof value === 'object' && 'after' in value) return `${key}: ${value.after}`
      return `${key}: ${Array.isArray(value) ? value.join('、') : value}`
    }).join('；') || '—'
  }
  return '—'
}

function memberName(memberId) {
  if (!memberId) return '未绑定'
  return props.members.find(m => Number(m.id) === Number(memberId))?.name || `成员#${memberId}`
}

function memberOptionLabel(member) {
  const generation = (member?.generation !== null && member?.generation !== undefined) ? `${member.generation}世` : '未分世代'
  const branch = member?.branch ? ` · ${member.branch}` : ''
  return `${member?.name || '未命名成员'}（${generation}${branch}）`
}

function scopeHint(role, memberId) {
  if (role === 'super_admin' || role === 'admin') return '全量范围，不受成员绑定限制'
  if (!memberId) return '未绑定成员时，该账号将看不到任何成员数据'
  if (role === 'editor') return `将限制为「${memberName(memberId)}」族人视角：完整可见本人/直系，基础可见兄弟姐妹、堂表亲及后代`
  if (role === 'viewer') return `当前为「${memberName(memberId)}」族人视角只读：完整可见本人/直系，基础可见兄弟姐妹、堂表亲及后代`
  return '该账号会按绑定成员限制可见范围'
}

function jumpTab(tab) {
  activeGovernanceTab.value = tab || 'overview'
}

function submit() {
  emit('save-settings', { ...draft })
}

function openUserDialog(user = null) {
  editingUser.value = user
  Object.assign(userDraft, {
    username: user?.username || '',
    password: '',
    displayName: user?.displayName || '',
    role: user?.role || 'viewer',
    memberId: user?.memberId ?? null,
    email: user?.email || '',
    phone: user?.phone || '',
    isActive: user?.isActive !== false,
  })
  userDialogVisible.value = true
}

function saveUser() {
  const payload = { ...userDraft }
  if (editingUser.value?.id) {
    delete payload.username
    delete payload.password
    emit('update-user', { id: editingUser.value.id, payload, done: () => { userDialogVisible.value = false } })
  } else {
    emit('create-user', { payload, done: () => { userDialogVisible.value = false } })
  }
}

function toggleUserActive(user) {
  emit('toggle-user-active', user)
}

function openPasswordDialog(user) {
  passwordUser.value = user
  newPassword.value = ''
  passwordDialogVisible.value = true
}

function resetPassword() {
  emit('reset-user-password', {
    id: passwordUser.value?.id,
    password: newPassword.value,
    done: () => { passwordDialogVisible.value = false },
  })
}

function qualitySeverity(level) {
  return props.qualityReport?.summary?.bySeverity?.[level] || 0
}

function qualitySeverityLabel(level) {
  return { error: '错误', warning: '警告', info: '提示' }[level] || level
}

function qualityTagType(level) {
  return { error: 'danger', warning: 'warning', info: 'info' }[level] || 'info'
}

function reviewStatusLabel(status) {
  return { pending: '待审核', approved: '已通过', rejected: '已驳回' }[status] || status
}

function reviewTagType(status) {
  return { pending: 'warning', approved: 'success', rejected: 'info' }[status] || 'info'
}

function reviewDiffText(row) {
  const diff = row?.diff || {}
  const entries = Object.entries(diff)
  if (!entries.length) return '—'
  return entries.slice(0, 4).map(([key, value]) => `${key}: ${value?.before ?? '空'} → ${value?.after ?? '空'}`).join('；')
}

function rejectReview(row) {
  const note = typeof window !== 'undefined' ? window.prompt('请输入驳回原因（可选）', '') : ''
  emit('reject-review', { row, note })
}

function openSourceDialog(source = null) {
  editingSource.value = source
  Object.assign(sourceDraft, {
    title: source?.title || '',
    source_type: source?.sourceType || '',
    author: source?.author || '',
    repository: source?.repository || '',
    reference: source?.reference || '',
    url: source?.url || '',
    note: source?.note || '',
  })
  sourceDialogVisible.value = true
}

function saveSource() {
  const payload = { ...sourceDraft }
  if (editingSource.value?.id) {
    emit('update-source', { id: editingSource.value.id, payload, done: () => { sourceDialogVisible.value = false } })
  } else {
    emit('create-source', { payload, done: () => { sourceDialogVisible.value = false } })
  }
}

// Family management methods
function openFamilyDialog(family = null) {
  editingFamily.value = family
  if (family) {
    Object.assign(familyForm, {
      name: family.name || '',
      surname: family.surname || '',
      siteTitle: family.siteTitle || '',
      subtitle: family.subtitle || '',
      coverKicker: family.coverKicker || '',
      description: family.description || '',
    })
  } else {
    Object.assign(familyForm, {
      name: '',
      surname: '',
      siteTitle: '',
      subtitle: '',
      coverKicker: '',
      description: '',
    })
  }
  familyDialogVisible.value = true
}

function saveFamily() {
  emit('save-family', { family: editingFamily.value, form: { ...familyForm }, done: () => { familyDialogVisible.value = false } })
}

async function manageFamilyUsers(family) {
  currentFamilyForUsers.value = family
  emit('load-family-users', { familyId: family.id, callback: (users) => { familyUsers.value = users } })
  familyUsersDialogVisible.value = true
}

function openAddFamilyUserDialog() {
  Object.assign(newFamilyUser, { userId: null, role: 'viewer' })
  addFamilyUserDialogVisible.value = true
}

function addFamilyUser() {
  if (!newFamilyUser.userId || !currentFamilyForUsers.value) return
  emit('add-family-user', {
    familyId: currentFamilyForUsers.value.id,
    userId: newFamilyUser.userId,
    role: newFamilyUser.role,
    done: () => {
      addFamilyUserDialogVisible.value = false
      emit('load-family-users', { familyId: currentFamilyForUsers.value.id, callback: (users) => { familyUsers.value = users } })
    }
  })
}

function removeFamilyUser(user) {
  if (!currentFamilyForUsers.value) return
  emit('remove-family-user', {
    familyId: currentFamilyForUsers.value.id,
    userId: user.userId,
    done: () => {
      emit('load-family-users', { familyId: currentFamilyForUsers.value.id, callback: (users) => { familyUsers.value = users } })
    }
  })
}

watch(() => props.settings, resetDraft, { immediate: true, deep: true })
</script>

<style scoped>
.settings-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.governance-hero {
  padding: 24px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top right, rgba(197, 155, 107, 0.26), transparent 34%),
    linear-gradient(135deg, rgba(255, 250, 242, 0.98), rgba(246, 237, 224, 0.92));
}

.governance-hero__main {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: flex-start;
}

.governance-hero__copy {
  max-width: 760px;
}

.governance-hero__eyebrow {
  margin: 0 0 6px;
  color: #9c6a3a;
  font-size: 12px;
  letter-spacing: 0.14em;
  font-weight: 700;
}

.governance-hero h2 {
  margin: 0 0 8px;
  color: #5f4228;
  font-size: 26px;
}

.governance-hero p {
  margin: 0;
  color: #7d644b;
  line-height: 1.75;
}

.governance-hero__actions,
.section-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.governance-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.governance-kpi-card {
  text-align: left;
  border: 1px solid rgba(190, 162, 127, 0.22);
  background: rgba(255, 255, 255, 0.82);
  border-radius: 20px;
  padding: 16px 18px;
  cursor: pointer;
  box-shadow: 0 14px 32px rgba(84, 57, 31, 0.06);
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}

.governance-kpi-card:hover {
  transform: translateY(-2px);
  border-color: rgba(156, 106, 58, 0.36);
  box-shadow: 0 18px 40px rgba(84, 57, 31, 0.10);
}

.governance-kpi-card span,
.governance-kpi-card small {
  display: block;
}

.governance-kpi-card span {
  color: #8b7154;
  font-size: 13px;
  margin-bottom: 8px;
}

.governance-kpi-card strong {
  display: block;
  color: #5f4228;
  font-size: 30px;
  line-height: 1;
  margin-bottom: 8px;
}

.governance-kpi-card small {
  color: #9a8064;
  line-height: 1.5;
}

.governance-kpi-card.is-danger strong { color: #b34b43; }
.governance-kpi-card.is-warning strong { color: #b4782f; }
.governance-kpi-card.is-source strong { color: #477b58; }
.governance-kpi-card.is-audit strong { color: #536f9e; }

.governance-tabs {
  border: none;
  border-radius: 22px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 18px 44px rgba(84, 57, 31, 0.08);
}

.governance-tabs :deep(.el-tabs__header) {
  background: rgba(248, 241, 231, 0.92);
  border-bottom: 1px solid rgba(190, 162, 127, 0.24);
}

.governance-tabs :deep(.el-tabs__item) {
  height: 48px;
  color: #7d644b;
  font-weight: 600;
}

.governance-tabs :deep(.el-tabs__item.is-active) {
  color: #6d3f1f;
  background: rgba(255, 255, 255, 0.86);
}

.governance-tabs :deep(.el-tabs__content) {
  padding: 16px;
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 16px;
  align-items: start;
}

.overview-card {
  min-height: 100%;
}

.section-card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.section-card-header p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.6;
  font-weight: 400;
}

.task-list,
.governance-notes,
.future-list.compact {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-item {
  width: 100%;
  text-align: left;
  border: 1px solid rgba(190, 162, 127, 0.22);
  background: rgba(255, 250, 242, 0.68);
  border-radius: 16px;
  padding: 13px 14px;
  cursor: pointer;
  transition: border-color .18s ease, background .18s ease;
}

.task-item:hover {
  background: rgba(255, 255, 255, 0.92);
  border-color: rgba(156, 106, 58, 0.35);
}

.task-item b,
.empty-governance-state b {
  display: block;
  color: #5f4228;
  margin-bottom: 5px;
}

.task-item span,
.empty-governance-state span {
  color: #7d644b;
  line-height: 1.6;
  font-size: 13px;
}

.task-item.is-danger {
  border-color: rgba(179, 75, 67, 0.28);
  background: rgba(255, 242, 240, 0.8);
}

.task-item.is-warning {
  border-color: rgba(180, 120, 47, 0.28);
  background: rgba(255, 247, 232, 0.86);
}

.empty-governance-state {
  padding: 18px;
  border-radius: 16px;
  background: rgba(247, 250, 246, 0.82);
  border: 1px dashed rgba(135, 168, 120, 0.45);
}

.quality-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.compact-issue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.compact-issue-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px dashed rgba(190, 162, 127, 0.24);
}

.compact-issue-item:last-child {
  border-bottom: none;
}

.compact-issue-item b,
.governance-note-item b,
.future-list.compact b {
  color: #5f4228;
  font-size: 13px;
}

.compact-issue-item span,
.governance-note-item span,
.future-list.compact span {
  display: block;
  color: #7d644b;
  font-size: 13px;
  line-height: 1.55;
  margin-top: 3px;
}

.governance-note-item,
.future-list.compact > div {
  padding: 10px 0;
  border-bottom: 1px dashed rgba(190, 162, 127, 0.26);
}

.governance-note-item:last-child,
.future-list.compact > div:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.permission-guide-card :deep(.el-card__body) {
  padding: 4px 16px;
}

.permission-guide-collapse,
.permission-guide-collapse :deep(.el-collapse-item__header),
.permission-guide-collapse :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.permission-guide-collapse :deep(.el-collapse-item__content) {
  padding-bottom: 12px;
}

.permission-guide-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.35;
}

.permission-guide-title strong {
  color: #5f4228;
  font-size: 14px;
}

.permission-guide-title span {
  color: #9a8064;
  font-size: 12px;
  font-weight: 400;
}

.source-guidance {
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(247, 250, 246, 0.86);
  color: #6f624f;
  line-height: 1.7;
  font-size: 13px;
}

.source-guidance b {
  color: #477b58;
}

.settings-config-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(360px, 1.1fr);
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .governance-hero__main {
    flex-direction: column;
  }

  .governance-hero__actions,
  .section-actions {
    justify-content: flex-start;
  }

  .governance-kpi-grid,
  .overview-grid,
  .settings-config-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .governance-kpi-grid,
  .overview-grid,
  .settings-config-grid {
    grid-template-columns: 1fr;
  }

  .section-card-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
