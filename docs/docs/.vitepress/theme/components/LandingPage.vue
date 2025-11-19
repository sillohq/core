<template>
  <div class="min-h-screen bg-gradient-to-br from-[#f9e6c7] via-[#f7dcb7] to-[#eecda2]">
    <!-- Hero Section -->
    <div class="relative overflow-hidden">
      <div class="absolute inset-0 bg-gradient-to-r from-[#8bcf6c]/20 to-[#f7b7a3]/20"></div>
      <div class="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-20 pb-32">
        <div class="text-center">
          <!-- Nexios Logo with Glow -->
          <div class="mb-8 flex justify-center">
            <div class="relative">
              <div class="absolute inset-0 bg-[#8bcf6c] rounded-full blur-xl opacity-60 animate-pulse"></div>
              <div class="relative bg-white/90 backdrop-blur-sm rounded-2xl p-8 shadow-2xl border border-[#8bcf6c]/30">
                <h1 class="text-6xl md:text-8xl font-bold bg-gradient-to-r from-[#8bcf6c] to-[#6cad55] bg-clip-text text-transparent">
                  Nexios
                </h1>
              </div>
            </div>
          </div>
          
          <!-- Hero Text -->
          <h2 class="text-2xl md:text-4xl font-semibold text-[#3a2a1d] mb-6 max-w-4xl mx-auto leading-tight">
            Build high-performance async APIs with clean architecture, zero boilerplate, and excellent developer experience
          </h2>
          
          <p class="text-lg md:text-xl text-[#3a2a1d]/80 mb-12 max-w-2xl mx-auto">
            The modern Python web framework that makes async development a breeze
          </p>
          
          <!-- CTA Buttons -->
          <div class="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <a href="/getting-started" class="px-8 py-4 bg-[#8bcf6c] hover:bg-[#6cad55] text-white font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105">
              Get Started
            </a>
            <a href="/why-nexios" class="px-8 py-4 bg-[#f7b7a3] hover:bg-[#f49d8d] text-[#3a2a1d] font-semibold rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105 border border-[#3a2a1d]/20">
              Why Nexios?
            </a>
          </div>
        </div>
      </div>
    </div>

    <!-- Features Section -->
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
      <div class="text-center mb-16">
        <h2 class="text-4xl md:text-5xl font-bold text-[#3a2a1d] mb-4">
          Why Developers Love Nexios
        </h2>
        <p class="text-xl text-[#3a2a1d]/70 max-w-2xl mx-auto">
          Powerful features that make async Python development intuitive and enjoyable
        </p>
      </div>
      
      <!-- Asymmetrical Feature Cards -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        <!-- Card 1 - Large -->
        <div class="lg:col-span-2 bg-white/80 backdrop-blur-sm rounded-2xl p-8 shadow-xl border border-[#8bcf6c]/20 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
          <div class="flex items-center mb-4">
            <div class="w-12 h-12 bg-[#8bcf6c] rounded-xl flex items-center justify-center mr-4">
              <span class="text-2xl">⚡</span>
            </div>
            <h3 class="text-2xl font-bold text-[#3a2a1d]">Lightning Fast</h3>
          </div>
          <p class="text-[#3a2a1d]/80 text-lg leading-relaxed">
            Built on modern async/await patterns with optimized performance. Handle thousands of concurrent requests with minimal resource usage.
          </p>
        </div>
        
        <!-- Card 2 - Small -->
        <div class="bg-gradient-to-br from-[#f7b7a3] to-[#f49d8d] rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
          <div class="text-center">
            <div class="w-16 h-16 bg-white/90 rounded-xl flex items-center justify-center mx-auto mb-4">
              <span class="text-3xl">🎯</span>
            </div>
            <h3 class="text-xl font-bold text-[#3a2a1d] mb-3">Zero Boilerplate</h3>
            <p class="text-[#3a2a1d]/80">Clean, minimal code that focuses on what matters</p>
          </div>
        </div>
        
        <!-- Card 3 - Medium -->
        <div class="bg-white/80 backdrop-blur-sm rounded-2xl p-6 shadow-xl border border-[#f7b7a3]/30 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-[#f7b7a3] rounded-lg flex items-center justify-center mr-3">
              <span class="text-xl">🏗️</span>
            </div>
            <h3 class="text-xl font-bold text-[#3a2a1d]">Clean Architecture</h3>
          </div>
          <p class="text-[#3a2a1d]/80">
            Structured patterns that scale from prototypes to production applications
          </p>
        </div>
        
        <!-- Card 4 - Medium -->
        <div class="lg:col-span-2 bg-gradient-to-r from-[#8bcf6c]/10 to-[#f7b7a3]/10 backdrop-blur-sm rounded-2xl p-6 shadow-xl border border-[#8bcf6c]/20 hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2">
          <div class="flex items-center mb-4">
            <div class="w-10 h-10 bg-[#8bcf6c] rounded-lg flex items-center justify-center mr-3">
              <span class="text-xl">🚀</span>
            </div>
            <h3 class="text-xl font-bold text-[#3a2a1d]">Developer Experience</h3>
          </div>
          <p class="text-[#3a2a1d]/80">
            Intuitive APIs, excellent error messages, and comprehensive documentation make development a joy
          </p>
        </div>
      </div>
    </div>

    <!-- What People Are Saying -->
    <div class="bg-white/50 backdrop-blur-sm py-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-16">
          <h2 class="text-4xl md:text-5xl font-bold text-[#3a2a1d] mb-4">
            What People Are Saying
          </h2>
          <p class="text-xl text-[#3a2a1d]/70">
            Developers around the world are building amazing things with Nexios
          </p>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          <!-- Testimonial 1 -->
          <div class="bg-white/80 backdrop-blur-sm rounded-2xl p-6 shadow-lg border border-[#8bcf6c]/20">
            <div class="flex items-center mb-4">
              <div class="w-12 h-12 bg-[#8bcf6c] rounded-full flex items-center justify-center text-white font-bold mr-4">
                S
              </div>
              <div>
                <h4 class="font-semibold text-[#3a2a1d]">Sarah Chen</h4>
                <p class="text-[#3a2a1d]/60 text-sm">Senior Backend Engineer</p>
              </div>
            </div>
            <p class="text-[#3a2a1d]/80 italic">
              "Nexios transformed how we build APIs. The clean architecture and async patterns made our codebase so much more maintainable."
            </p>
          </div>
          
          <!-- Testimonial 2 -->
          <div class="bg-white/80 backdrop-blur-sm rounded-2xl p-6 shadow-lg border border-[#f7b7a3]/20">
            <div class="flex items-center mb-4">
              <div class="w-12 h-12 bg-[#f7b7a3] rounded-full flex items-center justify-center text-[#3a2a1d] font-bold mr-4">
                M
              </div>
              <div>
                <h4 class="font-semibold text-[#3a2a1d]">Marcus Rodriguez</h4>
                <p class="text-[#3a2a1d]/60 text-sm">Tech Lead</p>
              </div>
            </div>
            <p class="text-[#3a2a1d]/80 italic">
              "The performance improvements were immediate. We're handling 3x more requests with the same infrastructure."
            </p>
          </div>
          
          <!-- Testimonial 3 -->
          <div class="bg-white/80 backdrop-blur-sm rounded-2xl p-6 shadow-lg border border-[#8bcf6c]/20">
            <div class="flex items-center mb-4">
              <div class="w-12 h-12 bg-[#8bcf6c] rounded-full flex items-center justify-center text-white font-bold mr-4">
                A
              </div>
              <div>
                <h4 class="font-semibold text-[#3a2a1d]">Alex Thompson</h4>
                <p class="text-[#3a2a1d]/60 text-sm">Full Stack Developer</p>
              </div>
            </div>
            <p class="text-[#3a2a1d]/80 italic">
              "Finally, a Python framework that makes async development intuitive. The documentation is fantastic too!"
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Brought to You By -->
    <div class="py-20">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 class="text-3xl md:text-4xl font-bold text-[#3a2a1d] mb-8">
          Brought to You By
        </h2>
        
        <div class="bg-white/80 backdrop-blur-sm rounded-3xl p-12 shadow-2xl border border-[#8bcf6c]/20">
          <div class="flex flex-col items-center">
            <!-- Nexios Logo -->
            <div class="relative mb-6">
              <div class="absolute inset-0 bg-[#8bcf6c] rounded-full blur-lg opacity-40"></div>
              <div class="relative bg-gradient-to-r from-[#8bcf6c] to-[#6cad55] rounded-2xl p-6 shadow-xl">
                <h3 class="text-4xl font-bold text-white">Nexios</h3>
              </div>
            </div>
            
            <p class="text-xl text-[#3a2a1d]/80 mb-6 max-w-2xl">
              A passionate team of developers dedicated to making Python web development more enjoyable and productive
            </p>
            
            <div class="flex flex-wrap gap-4 justify-center">
              <a href="https://github.com/nexios" class="px-6 py-3 bg-[#3a2a1d] hover:bg-[#2a1e14] text-white rounded-xl transition-colors duration-300">
                GitHub
              </a>
              <a href="/community" class="px-6 py-3 bg-[#f7b7a3] hover:bg-[#f49d8d] text-[#3a2a1d] rounded-xl transition-colors duration-300">
                Join Community
              </a>
              <a href="/contributing" class="px-6 py-3 border border-[#8bcf6c] text-[#8bcf6c] hover:bg-[#8bcf6c] hover:text-white rounded-xl transition-all duration-300">
                Contribute
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Component logic can go here if needed
</script>

<style scoped>
/* Component-specific styles can go here if needed */
</style>