<script setup lang="ts">
import type { SmartPlug, SmartPlugMeasure } from '@/api/Api'
import { useApiStore } from '@/stores/api'

const api = useApiStore()
const smartplugs: Ref<SmartPlug[]> = ref([])
const selected_smartplug_id: Ref<null | number> = ref(null)
const measures_of_selected_smartplug: Ref<SmartPlugMeasure[]> = ref([])
onMounted(async () => {
  reloadSmartplugs()
})
async function reloadSmartplugs() {
  smartplugs.value = await api.getSmartplugsList(1)
}

watch(selected_smartplug_id, async () => {
  if (selected_smartplug_id.value) {
    measures_of_selected_smartplug.value = await api.getSmartplugMeasures(1, selected_smartplug_id.value)
  }
})

async function createSmartplug() {
  const name = prompt('What is the name of the smartplug ?')
  if (!name || name.trim().length == 0) return
  const response = confirm("Can you confirm you want to create a new smartplug named '" + name + "' for installation 1 ?")
  if (response) {
    if (await api.createSmartplug(name, 1)) {
      reloadSmartplugs()
    }
  }
}

import { Chart as ChartJS, Title, Tooltip, Legend, LineElement, CategoryScale, LinearScale, LineController, PointElement } from 'chart.js'
import { computed, onMounted, ref, watch, type Ref } from 'vue'
import { Line } from 'vue-chartjs'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, LineController, Title, Tooltip, Legend)

function twodigits(number: number): string {
  if (number < 10) {
    return '0' + number.toString()
  }
  return number.toString()
}

const data = computed(() => {
  const values = measures_of_selected_smartplug.value.slice()
  return {
    labels: values.map((m) => {
      const date = new Date(m.time)
      return twodigits(date.getHours()) + ':' + twodigits(date.getMinutes())
    }),
    datasets: [{ label: 'Power consumption - W', data: values.map((m) => m.value), borderColor: 'blue' }]
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
  },
  maintainAspectRatio: false
}
</script>

<template>
  <div class="sm:flex gap-2">
    <div>
      <table class="w-full sm:w-auto">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="smartplug in smartplugs"
            :key="smartplug.id ?? 0"
            class="hover:bg-logo-o/20 cursor-pointer"
            :class="selected_smartplug_id == smartplug.id ? 'bg-logo-o/30' : ''"
            @click="selected_smartplug_id = smartplug.id ?? 0"
          >
            <td>{{ smartplug.id }}</td>
            <td>{{ smartplug.name }}</td>
          </tr>
        </tbody>
      </table>

      <button @click="createSmartplug">Create new smartplug</button>
    </div>

    <div class="min-h-[50vh] w-full h-full flex items-center justify-center border border-gray-300">
      <div v-if="selected_smartplug_id == null" class="text-gray-700">Please select a smartplug to show its measures.</div>
      <Line v-else :data="data" :options="chartOptions"></Line>
    </div>
  </div>
</template>
