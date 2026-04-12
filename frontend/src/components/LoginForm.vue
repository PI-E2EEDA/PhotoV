<script setup lang="ts">
import { ref } from 'vue';

const email = ref("")
const password = ref("")

function submit() {
  console.log("logging as " + email.value)
}
</script>

<template>
  <div class="max-w-60 m-auto h-[80vh] flex items-center">
    <div>
      <div>
        <label>Email</label>
        <input type="email" v-model="email" />
      </div>
      <div>
        <label>Password</label>
        <input type="password" v-model="password" />
      </div>

      <button @click="submit">Login</button>
    </div>
  </div>
</template>
