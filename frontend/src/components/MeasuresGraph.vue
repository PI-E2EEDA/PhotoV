<script setup lang="ts">
import type { Measure } from '@/api/Api';
const props = defineProps<{
  measures: Measure[]
}>()

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
import { computed } from 'vue';
import { Line } from 'vue-chartjs'

ChartJS.register(CategoryScale, LinearScale, LineElement, PointElement, LineController, Title, Tooltip, Legend)

// The colors are coming from the logo right now
const solar_production_color = "#0065f0"
const solar_consumption_color = "#6122b0"
const grid_consumption_color = "#ff8508"

function twodigits(number: number): string {
  if (number < 10) {
    return "0" + number.toString()
  }
  return number.toString()
}

const data = computed(() => {
  const reverse = props.measures.slice().reverse()
  return {
    labels: reverse.map((m) => {
      const date = new Date(m.time)
      return twodigits(date.getHours()) + ":" + twodigits(date.getMinutes())
    }),
    datasets: [
      { label: "Solar production", data: reverse.map(m => m.solar_production), borderColor: solar_production_color },
      { label: "Solar consumption", data: reverse.map(m => m.solar_consumption), borderColor: solar_consumption_color },
      { label: "Grid consumption", data: reverse.map(m => m.grid_consumption), borderColor: grid_consumption_color },

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
  <Line :data="data" :options="chartOptions"></Line>
</template>
