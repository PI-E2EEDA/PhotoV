<script setup lang="ts">
import { MeasureType, type Measure } from '@/api/Api';
import { useApiStore } from '@/stores/api';
import { onMounted, ref, watch, type Ref } from 'vue';
const api = useApiStore()
const ascending = ref(false)
const limit = ref(100)
const offset = ref(0)
const measures: Ref<Measure[]> = ref([])

async function reloadMeasures() {
  measures.value = await api.getLatestMeasure(MeasureType.Energy, ascending.value, limit.value, offset.value)
}
onMounted(async () => {
  await reloadMeasures()
})
watch(ascending, reloadMeasures)
watch(limit, reloadMeasures)
watch(offset, reloadMeasures)
</script>

<template>
  <div>
    <h2>Latest measures</h2>
    <div class="flex gap-2 items-center">
      <div><input type="checkbox" v-model="ascending" /> Ascending</div>
      <div><input type="number" v-model="limit" /> Limit</div>
      <div><input type="number" v-model="offset" /> Offset</div>
    </div>

    <div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Time</th>
            <th>Solar production</th>
            <th>Solar consumption</th>
            <th>Grid consumption</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="measure in measures" :key="measure.id ?? 0">
            <td>{{ measure.id }}</td>
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
