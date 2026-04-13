<script setup lang="ts">
import LandingPage from '@/components/LandingPage.vue';
import DashBoard from '@/components/DashBoard.vue';
import { useApiStore } from '@/stores/api';
const api = useApiStore()
</script>

<template>
  <LandingPage v-if="!api.logged"></LandingPage>
  <DashBoard v-if="api.logged">
  </DashBoard>
</template>
