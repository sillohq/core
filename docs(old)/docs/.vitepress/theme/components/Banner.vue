<script setup>
import { ref, onMounted, onUnmounted, watch, defineAsyncComponent } from 'vue'

const isVisible = ref(true)
const isDismissed = ref(false)
const currentBannerIndex = ref(0)
const bannerHeight = '40px'

// Array of banner components - people can import their own Vue component files here
const banners = [
  // Simple summary banner component
  {
    name: 'DocsSummary',
    component: defineAsyncComponent(() => import('./banners/DocsSummary.vue'))
  },
  
  // Mail banner component - people can create their own styled components
  {
    name: 'MailFeature',
    component: defineAsyncComponent(() => import('./banners/MailFeature.vue'))
  },

  // Another mail banner with different design
  {
    name: 'MailIntegration',
    component: defineAsyncComponent(() => import('./banners/MailIntegration.vue'))
  },

  // CLI banner component
  {
    name: 'CLIBanner',
    component: defineAsyncComponent(() => import('./banners/CLIBanner.vue'))
  },

  // Performance banner component
  {
    name: 'PerformanceBanner',
    component: defineAsyncComponent(() => import('./banners/PerformanceBanner.vue'))
  },

  // Community banner component
  {
    name: 'CommunityBanner',
    component: defineAsyncComponent(() => import('./banners/CommunityBanner.vue'))
  },

  // Bootstrap template banner component
  {
    name: 'BootstrapBanner',
    component: defineAsyncComponent(() => import('./banners/BootstrapBanner.vue'))
  }
]

let intervalId = null

const close = () => {
  isVisible.value = false
  isDismissed.value = true
  if (intervalId) {
    clearInterval(intervalId)
  }
}

const nextBanner = () => {
  currentBannerIndex.value = (currentBannerIndex.value + 1) % banners.length
}

const startSlideshow = () => {
  // Change banner every 4 seconds (between 3-6 seconds as requested)
  intervalId = setInterval(nextBanner, 4000)
}

const stopSlideshow = () => {
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
}

const handleScroll = () => {
  if (isDismissed.value) return

  if (window.scrollY > 10) {
    isVisible.value = false
    stopSlideshow()
  } else {
    isVisible.value = true
    startSlideshow()
  }
}

const updateLayout = () => {
  const root = document.documentElement
  if (isVisible.value) {
    root.style.setProperty('--banner-height', bannerHeight)
    document.body.classList.add('has-banner')
  } else {
    root.style.setProperty('--banner-height', '0px')
    document.body.classList.remove('has-banner')
  }
}

watch(isVisible, (newValue) => {
  updateLayout()
  if (newValue && !isDismissed.value) {
    startSlideshow()
  } else {
    stopSlideshow()
  }
})

onMounted(() => {
  updateLayout()
  window.addEventListener('scroll', handleScroll)
  startSlideshow()
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
  stopSlideshow()
})
</script>

<template>
  <transition name="banner-fade">
    <div v-if="isVisible" class="banner" role="alert">
      <div class="banner-content">
        <transition name="banner-slide" mode="out-in">
          <div :key="currentBannerIndex" class="banner-component-wrapper" @mouseenter="stopSlideshow" @mouseleave="startSlideshow">
            <!-- Render the current banner component from external files -->
            <component :is="banners[currentBannerIndex].component" @stop-slideshow="stopSlideshow" @start-slideshow="startSlideshow" />
          </div>
        </transition>
      </div>
      <button @click="close" class="close-btn" aria-label="Close banner">
        &times;
      </button>
    </div>
  </transition>
</template>

<style scoped>
.banner {
  background: rgba(139, 207, 108, 0.25);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(139, 207, 108, 0.3);
  color: var(--vp-c-text-1);
  height: var(--banner-height);
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 500;
  box-sizing: border-box;
}

.banner-content {
  flex: 1;
  text-align: center;
  position: relative;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.banner-component-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: inherit;
  opacity: 0.6;
  position:absolute;
  right:0;
  padding: 0 8px;
  line-height: 1;
  flex-shrink: 0;
}

.close-btn:hover {
  opacity: 1;
}

/* Banner fade transitions */
.banner-fade-enter-active,
.banner-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.banner-fade-enter-from,
.banner-fade-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}

/* Banner slide transitions for component changes */
.banner-slide-enter-active,
.banner-slide-leave-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}

.banner-slide-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.banner-slide-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .banner {
    font-size: 12px;
    padding: 0 12px;
  }
  
  .banner-component-wrapper {
    flex-direction: column;
    gap: 4px;
  }
}

/* Dark theme adjustments */
html.dark .banner {
  background: rgba(139, 207, 108, 0.15);
  border-bottom-color: rgba(139, 207, 108, 0.2);
}
</style>
