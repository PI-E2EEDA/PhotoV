<script setup lang="ts">
import type { SmartPlug, SmartPlugMeasure } from '@/api/Api';
import { useApiStore } from '@/stores/api';

const api = useApiStore()
const smartplugs: Ref<SmartPlug[]> = ref([])
const selected_smartplug_id: Ref<null | number> = ref(null)
const measures_of_selected_smartplug: Ref<SmartPlugMeasure[]> = ref([])
onMounted(async () => {
  smartplugs.value = await api.getSmartplugsList(1)
})

watch(selected_smartplug_id, async () => {
  if (selected_smartplug_id.value) {
    measures_of_selected_smartplug.value = await api.getSmartplugMeasures(1, selected_smartplug_id.value)
  }
})


import {
  Chart as ChartJS,
  Title,
  Tooltip,
  Legend,
  LineElement,
  CategoryScale,
  LinearScale,
  LineController,
  PointElement
} from 'chart.js'
import { computed, onMounted, ref, watch, type Ref } from 'vue';
import { Line } from 'vue-chartjs'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, LineController, Title, Tooltip, Legend)

function twodigits(number: number): string {
  if (number < 10) {
    return "0" + number.toString()
  }
  return number.toString()
}

const data = computed(() => {
  const reverse = measures_of_selected_smartplug.value.slice().reverse()
  return {
    labels: reverse.map((m) => {
      const date = new Date(m.time)
      return twodigits(date.getHours()) + ":" + twodigits(date.getMinutes())
    }),
    datasets: [
      { label: "Power consumption", data: reverse.map(m => m.value), borderColor: "blue" },

    ]
  }
})

const chartOptions = {
  responsive: true,
  scales: {
    x: {
      ticks: {
        maxTicksLimit: 60
      }
    }
  }
}
</script>

<template>

  <div class="flex gap-2">
    <div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="smartplug in smartplugs" :key="smartplug.id ?? 0" class="hover:bg-logo-o/20 cursor-pointer"
            :class="selected_smartplug_id == smartplug.id ? 'bg-logo-o/30' : ''"
            @click="selected_smartplug_id = smartplug.id ?? 0">
            <td>{{ smartplug.id }}</td>
            <td>{{ smartplug.name }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="min-h-72 w-full h-full flex items-center justify-center border border-gray-300">
      <div v-if="selected_smartplug_id == null" class="text-gray-700">Please select a smartplug to show its measures.
      </div>
      <Line v-else :data="data" :options="chartOptions"></Line>
    </div>
  </div>
</template>
