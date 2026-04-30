<script setup lang="ts">
import { useApiStore } from '@/stores/api'

const api = useApiStore()
function copyToken() {
  navigator.clipboard.writeText(api.token)
  alert('Done !')
}
</script>
<template>
  <div class="about">
    <h1>About</h1>

    You are logged in with account TODO and here are your tokens. hide if logged out ! transform as /user logout button without revoking token

    <div>
      <h3>Access the current API token</h3>
      <p class="font-bold">A token is as sensible as a password, make sure to keep it secret !</p>
      <p>Note: when you logged out here it will be revoked !</p>
      <button @click="copyToken">Copy to clipboard</button>
    </div>
  </div>

  <div>
    <h2>Credits</h2>
    The data displayed in PhotoV is coming from various sources:
    <ul>
      <li><strong>MeteoSwiss</strong> for the solar prediction and weather history. <a href="https://opendatadocs.meteoswiss.ch/e-forecast-data/e4-local-forecast-data">See docs</a></li>
      <li>
        <strong>SolarEdge</strong> is the source of measures for solar consumption, solar and grid consumption.
        <a href="https://knowledge-center.solaredge.com/sites/kc/files/se_monitoring_api.pdf">See their API docs</a>
      </li>
      <li><strong>Smartplugs data</strong> is provided by our projects using Swissdomotics smartplugs.</li>
    </ul>
  </div>
</template>
