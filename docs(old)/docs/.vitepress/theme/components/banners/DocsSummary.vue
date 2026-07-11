<template>
  <div class="docs-summary-banner">
    <span class="banner-text">Short on time? Check out our</span>
    <a href="/summary" class="banner-link" @click="navigateToSummary">docs summary</a>
  </div>
</template>

<script setup>
const navigateToSummary = (e) => {
  e.preventDefault()
  window.location.href = '/summary'
}
</script>

<style scoped>
.docs-summary-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
}

.banner-text {
  color: var(--vp-c-text-1);
}

.banner-link {
  color: var(--vp-c-brand-1);
  text-decoration: none;
  font-weight: 600;
  transition: opacity 0.2s;
  white-space: nowrap;
}

.banner-link:hover {
  opacity: 0.8;
  text-decoration: underline;
}

@media (max-width: 768px) {
  .docs-summary-banner {
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
  }
}
</style>
