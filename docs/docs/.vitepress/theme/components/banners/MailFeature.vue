<template>
  <div class="mail-feature-banner">
    <div class="mail-icon">📧</div>
    <span class="banner-text">Send emails easily with</span>
    <a href="/community/integrations/mail" class="mail-link" @click="navigateToMail">Nexios Mail</a>
  </div>
</template>

<script setup>
const navigateToMail = (e) => {
  e.preventDefault()
  window.location.href = '/community/integrations/mail'
}
</script>

<style scoped>
.mail-feature-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(37, 99, 235, 0.1));
  padding: 6px 16px;
  border-radius: 24px;
  border: 1px solid rgba(59, 130, 246, 0.2);
  font-size: 14px;
  font-weight: 500;
}

.mail-icon {
  font-size: 16px;
  margin-right: 4px;
}

.banner-text {
  color: var(--vp-c-text-1);
}

.mail-link {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: white;
  text-decoration: none;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 16px;
  transition: all 0.2s;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
}

.mail-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
  opacity: 0.9;
}

@media (max-width: 768px) {
  .mail-feature-banner {
    flex-direction: column;
    gap: 6px;
    padding: 8px 12px;
    font-size: 12px;
  }
  
  .mail-icon {
    margin-right: 0;
  }
}

/* Dark theme adjustments */
html.dark .mail-feature-banner {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.05), rgba(37, 99, 235, 0.05));
  border-color: rgba(59, 130, 246, 0.1);
}
</style>
