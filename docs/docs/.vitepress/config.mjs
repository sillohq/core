import { defineConfig } from 'vitepress'
import { navigation } from './config/navigation.mjs'
import { sidebarIntro, sidebarCommunity, sidebarApiReference, sidebarGuide } from './config/sidebar-main.mjs'
import { sidebarV2 } from './config/sidebar-v2.mjs'
import { themeConfig } from './config/theme.mjs'
import { transformHead } from './config/utilities.mjs'

export default defineConfig({
  transformHead,

  head: [

    ['link', { rel: 'icon', href: '/favicon.ico' }],
    ['meta', { name: 'theme-color', content: '#ff7e17' }],
    ['meta', { property: 'og:title', content: "Nexios - Python Web Framework" }],
    ['meta', { property: 'og:description', content: "Nexios is a modern, fast, and secure web framework for Python. It is designed to be easy to use and understand, while also being powerful and flexible." }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'twitter:site', content: '@nexioslabs' }],
  ],


  title: 'Nexios',
  // base: "/nexios/",
  description: 'Nexios is a modern, fast, and secure web framework for Python. It is designed to be easy to use and understand, while also being powerful and flexible.',

  themeConfig: {
    ...themeConfig,
    nav: navigation,
    sidebar: {
      '/intro/': sidebarIntro,
      '/community/': sidebarCommunity,
      '/api-reference/': sidebarApiReference,
      '/v2/guide/': sidebarV2,
      '/guide/': sidebarGuide
    }
  },

  markdown: {
    // lineNumbers: true
  },

  ignoreDeadLinks: true,
})
