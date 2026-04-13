import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { Api } from '@/api/Api'

export const useApiStore = defineStore('api', () => {
  const token = ref('')
  const domain = ref('')

  function getApi() {
    const api = new Api()
    api.baseUrl = 'https://' + domain.value
    return api
  }

  async function login(email: string, password: string): Promise<string | undefined> {
    console.log('logging as ' + email)
    const api = getApi()
    const result = await api.auth.authApiBearerDbAuthLoginAuthLoginPost(
      { username: email, password },
      {},
    )
    if (result.ok) {
      token.value = result.data.access_token
    } else {
      return result.error.detail?.toString()
    }
  }
  const doubleCount = computed(() => count.value * 2)

  return { domain, login, doubleCount }
})
