# frontend

## Overview
Here is the `tree src` at 2026-05-04
```sh
├── src
│   ├── api
│   │   ├── Api.ts # Automatically generated TS API client for our backend API
│   │   └── README.md
│   ├── App.vue # the App entrypoint
│   ├── assets
│   │   ├── logo.svg
│   │   └── main.css # global CSS style
│   ├── components # small compoments used in various views
│   │   ├── DashBoard.vue
│   │   ├── LandingPage.vue
│   │   ├── LoginForm.vue
│   │   ├── MeasuresGraph.vue
│   │   └── SmartplugsDetails.vue
│   ├── main.ts
│   ├── router # the router defining /about -> AboutView, ...
│   │   └── index.ts
│   ├── stores # The Pinia router
│   │   └── api.ts
│   └── views # each view corresponds to a page on the router
│       ├── AboutView.vue
│       ├── HomeView.vue
│       ├── LoginView.vue
│       └── SmartplugsView.vue
```

## Getting started with VueJS
Here are a few ressources that are recommended when getting started with VueJS development.

1. Install PNPM and NodeJS
1. Install the [Tailwind plugin for your IDE](https://tailwindcss.com/docs/editor-setup)
1. Install the [VueJS devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools) to inspect components state and Stores content
1. Checkout [IDE support](https://vuejs.org/guide/scaling-up/tooling.html#ide-support) to install useful extensions
1. Watch this short free course [Intro to Vue 3 (Composition API)](https://www.vuemastery.com/courses/intro-to-vue-3-comp-api/introduction-comp-api/)
1. Look at a simple component like `frontend/src/components/LoginForm.vue` to see what you learn in practice
1. Look at the [VueJS docs](https://vuejs.org/guide/essentials/application.html) in case more details are needed
1. Pinia provides a "global instance" where we can store data that need to be accessed from various components. Instead of passing down values via components properties, we make them globally accessible. Some of the attributes of our store are also persisted in the localStorage on each change. You can inspect `localStorage` in the browser console and change the server type on the login page. You can try to understand the Pinia syntax [by reading Setup Stores and Using the store on Pinia docs](https://pinia.vuejs.org/core-concepts/#Setup-Stores). 
1. Look at our Pinia stores inside `frontend/src/stores/`. Open the VueJS devtools, open the Pinia details and see the store change when loading smartplugs data.
1. We have various frontend only routes like `/login`, `/`, `/about`, etc... To learn how it works, read the entire page on [Vue Router](https://router.vuejs.org/guide/). Open the VueJS devtools, open the Vue Router details and see the routes definition.
1. Look our frontend routes definition in `frontend/src/router/index.ts`

Try to develop the next feature !

---

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
pnpm install
```

### Compile and Hot-Reload for Development

```sh
pnpm dev
```

### Type-Check, Compile and Minify for Production

```sh
pnpm build
```

### Run Unit Tests with [Vitest](https://vitest.dev/)

```sh
pnpm test:unit
```

### Lint with [ESLint](https://eslint.org/)

```sh
pnpm lint
```
