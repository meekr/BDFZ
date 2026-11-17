import { defineConfig } from 'vite';

// 相对路径，dist/ 可直接放到任意静态目录下
export default defineConfig({
  base: './',
  build: { chunkSizeWarningLimit: 800 },
});
