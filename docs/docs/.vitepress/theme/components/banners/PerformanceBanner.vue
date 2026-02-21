<template>
  <div class="performance-banner">
    <div class="performance-icon">⚡</div>
    <span class="banner-text">Performance optimized for production</span>
    <a href="/guide/deployment" class="performance-link" @click="navigateToDeployment">deploy now</a>
  </div>
</template>

<script setup>
const navigateToDeployment = (e) => {
  e.preventDefault()
  window.location.href = '/guide/deployment'
}
</script>

<style scoped>
.performance-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.1));
  padding: 6px 16px;
  border-radius: 24px;
  border: 1px solid rgba(16, 185, 129, 0.2);
  font-size: 14px;
  font-weight: 500;
}

.performance-icon {
  font-size: 16px;
  margin-right: 4px;
}

.banner-text {
  color: var(--vp-c-text-1);
}

.performance-link {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  text-decoration: none;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 16px;
  transition: all 0.2s;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(16, 185, 129, 0.2);
}

.performance-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(16, 185, 129, 0.3);
  opacity: 0.9;
}

@media (max-width: 768px) {
  .performance-banner {
    flex-direction: column;
    gap: 6px;
    padding: 8px 12px;
    font-size: 12px;
  }
  
  .performance-icon {
    margin-right: 0;
  }
}

/* Dark theme adjustments */
html.dark .performance-banner {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.05), rgba(5, 150, 105, 0.05));
  border-color: rgba(16, 185, 129, 0.1);
}
</style>
