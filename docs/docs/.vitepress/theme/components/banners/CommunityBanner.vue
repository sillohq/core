<template>
  <div class="community-banner">
    <div class="community-icon">💬</div>
    <span class="banner-text">Join our community on</span>
    <a href="https://github.com/nexios-labs/nexios/discussions" 
       class="community-link" 
       target="_blank" 
       rel="noopener noreferrer"
       @click="navigateToCommunity">GitHub Discussions</a>
  </div>
</template>

<script setup>
const navigateToCommunity = (e) => {
  e.preventDefault()
  window.open('https://github.com/nexios-labs/nexios/discussions', '_blank')
}
</script>

<style scoped>
.community-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
}

.community-icon {
  font-size: 16px;
  margin-right: 4px;
}

.banner-text {
  color: var(--vp-c-text-1);
}

.community-link {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: white;
  text-decoration: none;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 16px;
  transition: all 0.2s;
  white-space: nowrap;
  box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2);
}

.community-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(99, 102, 241, 0.3);
  opacity: 0.9;
}

@media (max-width: 768px) {
  .community-banner {
    flex-direction: column;
    gap: 6px;
    font-size: 12px;
  }
  
  .community-icon {
    margin-right: 0;
  }
}
</style>
