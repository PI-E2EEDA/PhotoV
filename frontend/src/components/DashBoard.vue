<script setup lang="ts">
import { MeasureType, type Measure } from '@/api/Api'
import { useApiStore } from '@/stores/api'
import { computed, onMounted, ref, watch, type Ref } from 'vue'
import MeasuresGraph from './MeasuresGraph.vue'
const api = useApiStore()
const type = ref(MeasureType.Power)
const ascending = ref(false)
const limit = ref(100)
const offset = ref(0)
const measures: Ref<Measure[]> = ref([])
const unit = computed(() => {
  return type.value == MeasureType.Energy ? 'Wh' : 'W'
})

async function reloadMeasures() {
  measures.value = await api.getLatestMeasures(type.value, ascending.value, limit.value, offset.value)
}
onMounted(async () => {
  await reloadMeasures()
})
watch(type, reloadMeasures)
watch(ascending, reloadMeasures)
watch(limit, reloadMeasures)
watch(offset, reloadMeasures)

const QUARTER_PER_DAYS = 96
function shiftDayBefore(increment: number) {
  const new_offset = offset.value + increment * QUARTER_PER_DAYS

  if (new_offset > 0) {
    offset.value = new_offset
  }
}

const isNextDayDisabled = computed(() => {
  return offset.value - QUARTER_PER_DAYS < 0
})
</script>

<template>
  <div>
    <h2>Latest measures</h2>
    <div class="min-h-[50vh] w-full">
      <MeasuresGraph :measures="measures"></MeasuresGraph>
    </div>
    <div class="flex flex-wrap gap-x-4 items-center">
      <div>
        Type:
        <select v-model="type">
          <option :value="MeasureType.Energy">Energy</option>
          <option :value="MeasureType.Power">Power</option>
        </select>
      </div>
      <div><input type="checkbox" v-model="ascending" /> Ascending</div>
      <div>Limit: <input type="number" v-model="limit" class="max-w-24" /></div>
      <div>Offset: <input type="number" v-model="offset" class="max-w-16" /></div>
      <button @click="shiftDayBefore(1)">Previous day</button>
      <button @click="shiftDayBefore(-1)" :disabled="isNextDayDisabled">Next day</button>
    </div>

    <div>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Solar production {{ unit }}</th>
            <th>Solar consumption {{ unit }}</th>
            <th>Grid consumption {{ unit }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="measure in measures" :key="measure.id ?? 0">
            <td>{{ measure.time }}</td>
            <td>{{ measure.solar_production }}</td>
            <td>{{ measure.solar_consumption }}</td>
            <td>{{ measure.grid_consumption }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
