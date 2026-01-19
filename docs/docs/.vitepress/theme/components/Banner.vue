<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'

const isVisible = ref(true)
const isDismissed = ref(false)
const bannerHeight = '40px'

const close = () => {
  isVisible.value = false
  isDismissed.value = true
}

const handleScroll = () => {
  if (isDismissed.value) return

  if (window.scrollY > 10) {
    isVisible.value = false
  } else {
    isVisible.value = true
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

watch(isVisible, updateLayout)

onMounted(() => {
  updateLayout()
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<template>
  <transition name="banner-fade">
    <div v-if="isVisible" class="banner" role="alert">
      <div class="banner-content">
        <span>⚠️ Nexios v2 has be deprecated </span>
        <a href="/changelog" class="banner-link">Read more</a>
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
  padding: 0 16px;
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
}

.banner-link {
  margin-left: 8px;
  color: var(--vp-c-brand-1);
  text-decoration: none;
  font-weight: 700;
  transition: opacity 0.2s;
}

.banner-link:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.close-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: inherit;
  opacity: 0.6;
  padding: 0 8px;
  line-height: 1;
}

.close-btn:hover {
  opacity: 1;
}

.banner-fade-enter-active,
.banner-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.banner-fade-enter-from,
.banner-fade-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}
</style>
