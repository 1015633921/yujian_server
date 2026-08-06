<script setup lang="ts">
import { computed, ref } from 'vue'
import PageErrorState from '@/components/ui/PageErrorState.vue'
import PageHeading from '@/components/ui/PageHeading.vue'
import { getDailyRules, saveDailyRules, type DailyRules } from '@/features/users/api'
import { useAuthStore } from '@/stores/auth'
const auth=useAuthStore(); const data=ref<DailyRules|null>(null); const text=ref(''); const loading=ref(true); const saving=ref(false); const message=ref(''); const error=ref(''); const canManage=computed(()=>auth.admin?.role!=='viewer')
async function load():Promise<void>{loading.value=true;error.value='';try{data.value=await getDailyRules();text.value=JSON.stringify(data.value.rules||{},null,2)}catch(cause){error.value=cause instanceof Error?cause.message:'规则加载失败'}finally{loading.value=false}}
function format():void{try{text.value=JSON.stringify(JSON.parse(text.value),null,2);message.value='已格式化。'}catch{message.value='JSON 格式错误，未提交。'}}
async function save(reset=false):Promise<void>{if(!canManage.value||saving.value)return;let rules:Record<string,unknown>={};if(!reset)try{rules=JSON.parse(text.value)}catch{message.value='JSON 格式错误，未提交。';return};if(reset&&!window.confirm('恢复默认会覆盖当前自定义规则，确定继续吗？'))return;saving.value=true;message.value='';try{data.value=await saveDailyRules(rules,reset);text.value=JSON.stringify(data.value.rules||{},null,2);message.value=reset?'已恢复系统默认规则。':'每日能量规则已保存。'}catch(cause){message.value=cause instanceof Error?cause.message:'保存失败。'}finally{saving.value=false}}
void load()
</script><template>
  <section class="workspace-page rules-page">
    <PageHeading
      eyebrow="DAILY ENERGY RULES"
      title="每日能量规则"
      description="控制小程序每日建议中的状态、场景、目标、五行权重和推荐晶石。"
    >
      <template #actions>
        <button
          class="heading-link"
          type="button"
          @click="load"
        >
          重新读取
        </button>
      </template>
    </PageHeading><PageErrorState
      v-if="error&&!loading"
      title="规则暂时无法读取"
      :message="error"
      eyebrow="RULES UNAVAILABLE"
      @retry="load"
    /><div
      v-else
      class="rules-editor"
    >
      <header><div><span>RULES VERSION</span><h2>{{ data?.rules_version||data?.public_options?.rules_version||'—' }}</h2></div><p>规则保存后，用户下次刷新每日建议会使用新版本。</p></header><textarea
        v-model="text"
        :disabled="!canManage||loading"
        spellcheck="false"
      /><footer>
        <button
          type="button"
          @click="format"
        >
          格式化
        </button><button
          type="button"
          :disabled="!canManage||saving"
          @click="save(true)"
        >
          恢复默认
        </button><button
          class="primary-action"
          type="button"
          :disabled="!canManage||saving"
          @click="save()"
        >
          {{ saving?'保存中…':'保存规则' }}
        </button><p>{{ message||(!canManage?'当前账号为只读，不能修改规则。':'') }}</p>
      </footer>
    </div>
  </section>
</template>
