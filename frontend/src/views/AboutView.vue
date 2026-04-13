<script setup>
import { useApiStore } from '@/stores/api';

const api = useApiStore()
function copyToken() {
  navigator.clipboard.writeText(api.token);
  alert("Done !")
}
</script>
<template>
  <div class="about">
    <h1>About</h1>

    <div>
      <h3>Access the current API token</h3>
      <p class="font-bold">A token is as sensible as a password, make sure to keep it secret !</p>
      <p>Note: when you logged out here it will be revoked !</p>
      <button @click="copyToken">Copy to clipboard</button>
    </div>
  </div>
</template>
