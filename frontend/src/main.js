import { createApp } from 'vue'
import { ElAlert } from 'element-plus/es/components/alert/index'
import { ElButton } from 'element-plus/es/components/button/index'
import { ElCard } from 'element-plus/es/components/card/index'
import { ElCheckbox, ElCheckboxGroup } from 'element-plus/es/components/checkbox/index'
import { ElCol } from 'element-plus/es/components/col/index'
import { ElCollapse, ElCollapseItem } from 'element-plus/es/components/collapse/index'
import { ElDatePicker } from 'element-plus/es/components/date-picker/index'
import { ElDialog } from 'element-plus/es/components/dialog/index'
import { ElDivider } from 'element-plus/es/components/divider/index'
import { ElDrawer } from 'element-plus/es/components/drawer/index'
import { ElEmpty } from 'element-plus/es/components/empty/index'
import { ElForm, ElFormItem } from 'element-plus/es/components/form/index'
import { ElInput } from 'element-plus/es/components/input/index'
import { ElInputNumber } from 'element-plus/es/components/input-number/index'
import { ElOption, ElSelect } from 'element-plus/es/components/select/index'
import { ElProgress } from 'element-plus/es/components/progress/index'
import { ElRadio, ElRadioButton, ElRadioGroup } from 'element-plus/es/components/radio/index'
import { ElRow } from 'element-plus/es/components/row/index'
import { ElSegmented } from 'element-plus/es/components/segmented/index'
import { ElSwitch } from 'element-plus/es/components/switch/index'
import { ElTabPane, ElTabs } from 'element-plus/es/components/tabs/index'
import { ElTable, ElTableColumn } from 'element-plus/es/components/table/index'
import { ElTag } from 'element-plus/es/components/tag/index'
import { ElTimeline, ElTimelineItem } from 'element-plus/es/components/timeline/index'
import { ElTooltip } from 'element-plus/es/components/tooltip/index'
import { ElUpload } from 'element-plus/es/components/upload/index'
import 'element-plus/dist/index.css'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import './style.css'
import App from './App.vue'
import router from './router'

const elementComponents = [
  ElAlert,
  ElButton,
  ElCard,
  ElCheckbox,
  ElCheckboxGroup,
  ElCol,
  ElCollapse,
  ElCollapseItem,
  ElDatePicker,
  ElDialog,
  ElDivider,
  ElDrawer,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElProgress,
  ElRadio,
  ElRadioButton,
  ElRadioGroup,
  ElRow,
  ElSegmented,
  ElSelect,
  ElSwitch,
  ElTabPane,
  ElTable,
  ElTableColumn,
  ElTabs,
  ElTag,
  ElTimeline,
  ElTimelineItem,
  ElTooltip,
  ElUpload,
]

const app = createApp(App)
app.use(router)
elementComponents.forEach(component => app.use(component))
app.mount('#app')
