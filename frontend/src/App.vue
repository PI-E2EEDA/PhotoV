<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { useApiStore } from './stores/api'

const api = useApiStore()
</script>

<template>
  <div class="p-2">
    <header class="flex py-2 border-b border-logo-p/30">
      <div class="flex-1 p-2 invisible sm:visible">
        <img alt="Vue logo" class="h-7" src="@/assets/logo.svg" />
      </div>

      <nav class="flex flex-wrap gap-3 items-center">
        <RouterLink to="/">Home</RouterLink>
        <RouterLink to="/smartplugs">Smartplugs</RouterLink>
        <RouterLink v-if="!api.logged" to="/login">Login</RouterLink>
        <RouterLink to="/about">About</RouterLink>
        <a v-if="api.logged" @click="api.logout()">Logout</a>
      </nav>
    </header>

    <RouterView />
  </div>
</template>
