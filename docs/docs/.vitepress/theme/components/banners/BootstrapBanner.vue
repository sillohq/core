<template>
  <div 
    class="bootstrap-banner"
    @mouseenter="stopSlideshow"
    @mouseleave="startSlideshow"
  >
    <div class="content">
      <span class="dot"></span>

      <span class="text">
        Backend made easy with 
        <strong>Nexios Bootstrap</strong>
      </span>

      <a
        href="https://github.com/nexios-labs/nexios-bootstrap"
        target="_blank"
        rel="noopener noreferrer"
        class="cta"
      >
        Clone Template →
      </a>
    </div>
  </div>
</template>

<script setup>
const emit = defineEmits(['stop-slideshow', 'start-slideshow'])

const stopSlideshow = () => emit('stop-slideshow')
const startSlideshow = () => emit('start-slideshow')
</script>

<style scoped>
.bootstrap-banner {
  width: 100%;
  padding: 10px 16px;
  background: linear-gradient(90deg, #0f0f14, #14141f);
  border-bottom: 1px solid rgba(255,255,255,0.05);
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 13px;
}

.content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #8b5cf6;
  box-shadow: 0 0 8px #8b5cf6;
}

.text {
  color: #d4d4d8;
  font-weight: 500;
}

.text strong {
  color: white;
  font-weight: 600;
}

.cta {
  color: #a78bfa;
  text-decoration: none;
  font-weight: 600;
  transition: all 0.2s ease;
}

.cta:hover {
  color: #c4b5fd;
  transform: translateX(2px);
}

@media (max-width: 768px) {
  .content {
    gap: 8px;
    font-size: 12px;
  }
}
</style>