<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="p-2">
    <header class="flex py-2 border-b border-logo-p/30">
      <div class="flex-1 p-2">
        <img alt="Vue logo" class="h-5" src="@/assets/logo.svg" />
      </div>

      <nav class="flex gap-3 items-center">
        <RouterLink to="/">Home</RouterLink>
        <RouterLink to="/login">Login</RouterLink>
        <RouterLink to="/about">About</RouterLink>
      </nav>
    </header>

    <RouterView />
  </div>
</template>
