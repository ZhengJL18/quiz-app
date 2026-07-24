<template>
  <div class="min-h-[60vh] flex items-center justify-center">
    <div class="text-center">
      <div class="text-8xl font-bold text-[var(--ink-muted)] mb-4">404</div>
      <p class="text-xl text-[var(--ink-primary)] mb-2">页面不存在</p>
      <p class="text-sm text-[var(--ink-muted)] mb-6">你访问的页面可能已被移动或删除</p>
      <router-link to="/" class="btn btn-primary px-8 py-3 font-medium no-underline inline-flex">
        返回首页
      </router-link>
    </div>
  </div>
</template>
