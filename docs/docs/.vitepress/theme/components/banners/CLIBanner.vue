<template>
  <div class="cli-banner">
    <span class="banner-text">Build faster with</span>
    <a href="/guide/cli" class="cli-link" @click="navigateToCLI">Nexios CLI</a>
  </div>
</template>

<script setup>
const navigateToCLI = (e) => {
  e.preventDefault()
  window.location.href = '/guide/cli'
}
</script>

<style scoped>
.cli-banner {
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

.cli-link {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: white;
  text-decoration: none;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 16px;
  transition: all 0.2s;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(245, 158, 11, 0.2);
  cursor: pointer;
}

.cli-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(245, 158, 11, 0.3);
  opacity: 0.9;
}

@media (max-width: 768px) {
  .cli-banner {
    flex-direction: column;
    gap: 6px;
    font-size: 12px;
  }
}
</style>
