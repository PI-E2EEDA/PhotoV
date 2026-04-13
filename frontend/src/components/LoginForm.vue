<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useApiStore } from '@/stores/api.ts';

const email = ref("")
const password = ref("")
const domain = ref("api.photov.srd.rs")
const error_text = ref("")
const api = useApiStore()

onMounted(() => {
  api.domain = domain.value
})

async function submit() {
  const result = await api.login(email.value, password.value)
  if (result) {
    error_text.value = result
  }
}

function updateDomain() {
  api.domain = domain.value
}
</script>

<template>
  <div class="max-w-60 m-auto h-[80vh] flex items-center">
    <div>
      <div class="flex">
        <label class="mr-3">Serveur: </label>
        <select v-model="domain" @change="updateDomain">
          <option value="localhost:8000">Development API</option>
          <option value="api.photov.srd.rs">Production API</option>
        </select>
      </div>
      <div>
        <label>Email</label>
        <input type="email" v-model="email" />
      </div>
      <div>
        <label>Password</label>
        <input type="password" v-model="password" />
      </div>

      <button @click="submit">Login</button>
      <div v-if="error_text.trim().length > 0">{{ error_text }}</div>
    </div>
  </div>
</template>
