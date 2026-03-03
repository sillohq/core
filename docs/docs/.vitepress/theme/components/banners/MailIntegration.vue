<template>
  <div class="mail-integration-banner">
    <div class="badge">NEW!</div>
    <div class="rocket-icon"></div>
    <span class="banner-text">Nexios Mail integration</span>
    <a href="/community/integrations/mail" class="integration-link" @click="navigateToMail">send emails</a>
  </div>
</template>

<script setup>
const navigateToMail = (e) => {
  e.preventDefault()
  window.location.href = '/community/integrations/mail'
}
</script>

<style scoped>
.mail-integration-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
}

.badge {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 700;
  margin-right: 4px;
  box-shadow: 0 2px 4px rgba(16, 185, 129, 0.3);
}

.rocket-icon {
  font-size: 16px;
  margin-right: 2px;
}

.banner-text {
  color: var(--vp-c-text-1);
}

.integration-link {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
  color: white;
  text-decoration: none;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 16px;
  transition: all 0.2s;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(139, 92, 246, 0.2);
}

.integration-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(139, 92, 246, 0.3);
  opacity: 0.9;
}

@media (max-width: 768px) {
  .mail-integration-banner {
    flex-direction: column;
    gap: 6px;
    font-size: 12px;
  }
  
  .badge {
    font-size: 8px;
    padding: 1px 6px;
  }
  
  .rocket-icon {
    margin-right: 0;
  }
}

/* Dark theme adjustments */
html.dark .badge {
  background: linear-gradient(135deg, #059669, #047857);
}
</style>
