<script setup lang="ts">

import { useApiStore } from '@/stores/api.ts';
import { ref } from 'vue';

const email = ref("")
const password = ref("")
const error_text = ref("")
const api = useApiStore()


async function submit() {
  const result = await api.login(email.value, password.value)
  if (result) {
    error_text.value = result
  }
}

</script>

<template>
  <div class="max-w-60 m-auto h-[80vh] flex items-center">
    <div>
      <h2>Login in PhotoV</h2>
      <div class="flex items-center">
        <label class="mr-3">Serveur</label>
        <select v-model="api.domain">
          <option value="localhost:8000">Development API</option>
          <option value="api.photov.srd.rs">Production API</option>
        </select>
      </div>
      <div>
        <label>Email</label>
        <input class="w-full" type="email" v-model="email" />
      </div>
      <div>
        <label>Password</label>
        <input class="w-full" type="password" v-model="password" />
      </div>

      <button @click="submit">Login</button>
      <div v-if="error_text.trim().length > 0">{{ error_text }}</div>
    </div>
  </div>
</template>
