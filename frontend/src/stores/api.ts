import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { Api, MeasureType, type Measure, type SmartPlug, type SmartPlugMeasure } from '@/api/Api'
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
      if (domain.value.includes('localhost:')) {
        // fastapi doesn't have HTTPS on localhost
        api.baseUrl = 'http://' + domain.value
      } else {
        api.baseUrl = 'https://' + domain.value
      }
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

    async function createSmartplug(name: string, installation_id: number): Promise<boolean> {
      const api = getApi()
      try {
        const result = await api.smartplugs.createSmartplugSmartplugsPost({ name, installation_id })
        return result.ok
      } catch (e) {
        alert(e)
        return false
      }
    }

    async function getLatestMeasures(
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

    async function getSmartplugMeasures(
      installation_id: number,
      smartplug_id: number,
    ): Promise<SmartPlugMeasure[]> {
      const api = getApi()
      try {
        const result =
          await api.smartplugs.getSmartplugMeasuresSmartplugsInstallationIdSmartplugIdGet(
            installation_id,
            smartplug_id,
          )
        if (result.ok) {
          return result.data
        }
      } catch (e) {
        console.log(e)
      }
      return []
    }

    async function getSmartplugsList(installation_id: number): Promise<SmartPlug[]> {
      const api = getApi()
      try {
        const result =
          await api.smartplugs.getSmartplugsSmartplugsInstallationIdGet(installation_id)
        if (result.ok) {
          return result.data
        }
      } catch (e) {
        console.log(e)
      }
      return []
    }

    // const doubleCount = computed(() => count.value * 2)

    return {
      domain,
      logged,
      login,
      logout,
      token,
      getLatestMeasures,
      getSmartplugsList,
      getSmartplugMeasures,
      createSmartplug,
    }
  },
  {
    persist: true,
  },
)
