import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { Api, MeasureType, type Measure } from '@/api/Api'
import { useRouter } from 'vue-router'

export const useApiStore = defineStore(
  'api',
  () => {
    const router = useRouter()
    const token = ref('')
    const logged = ref(false)
    const domain = ref('')

    function getApi() {
      let config = {}
      if (logged.value) {
        config = { baseApiParams: { headers: { Authorization: 'Bearer ' + token.value } } }
      }
      const api = new Api(config)
      api.baseUrl = 'https://' + domain.value
      api.setSecurityData({})
      return api
    }

    async function login(email: string, password: string): Promise<string | undefined> {
      console.log('logging as ' + email)
      const api = getApi()
      const result = await api.auth.authApiBearerDbAuthLoginAuthLoginPost({
        username: email,
        password,
      })
      if (result.ok) {
        token.value = result.data.access_token
        logged.value = true
        router.push({ name: 'home' })
      } else {
        return result.error.detail?.toString()
      }
    }

    async function logout() {
      const api = getApi()
      try {
        await api.auth.authApiBearerDbAuthLogoutAuthLogoutPost()
      } catch (e) {
        console.log(e)
      }
      token.value = ''
      logged.value = false
    }

    async function getLatestMeasure(
      type: MeasureType,
      ascending: boolean = false,
      limit = 100,
      offset = 0,
    ): Promise<Measure[]> {
      const api = getApi()
      try {
        const result = await api.measures.getMeasuresMeasuresInstallationIdTypeGet(1, type, {
          ascending,
          limit,
          offset,
        })
        if (result.ok) {
          return result.data
        }
      } catch (e) {
        console.log(e)
      }
      return []
    }

    // const doubleCount = computed(() => count.value * 2)

    return { domain, logged, login, logout, token, getLatestMeasure }
  },
  {
    persist: true,
  },
)
