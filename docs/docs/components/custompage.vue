

<template>
  <div class="container">
    <main class="main-content">
      <p class="headline">
        Nexios: <br />
        Lightweight. Fast. <br />
        Backend at Dollar Weight
      </p>
      <p class="subtext">
        Nexios is the minimal yet powerful backend framework that gets out of your way — fast, clean, async-firsta.
      </p>
      <a href="/guide/getting-started" class="btn">Get Started</a>
    </main>

    <footer class="footer">
      &copy; 2025 Nexios Labs. All rights reserved.
    </footer>
  </div>
</template>

<script setup>
// No logic needed
</script>

<style scoped>
.container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  width: 100%;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 1rem;
}

.headline {
  font-size: 2.5rem;
  font-weight: bold;
  line-height: 1.3;
  margin-bottom: 1.5rem;
}

@media (min-width: 768px) {
  .headline {
    font-size: 3rem;
  }
}

.subtext {
  max-width: 600px;
  margin-bottom: 2rem;
}

.btn {
  background-color: #4CAF50;
  padding: 0.75rem 1.5rem;
  border-radius: 9999px;
  font-size: 1.125rem;
  text-decoration: none;
  transition: background-color 0.3s ease;
}

.btn:hover {
  background-color: #333;
}

.footer {
  width: 100%;
  text-align: center;
  font-size: 0.875rem;
  color: #888;
  margin-top: 3rem;
}
</style>
