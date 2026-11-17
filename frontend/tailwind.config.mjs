/** Tailwind v4-compatible ESM configuration. CSS semantic tokens remain authoritative. */
export default {
  content: ['./index.html','./src/**/*.{ts,tsx}'],
  theme: {extend: {
    fontFamily: {
      sans:['Plus Jakarta Sans','system-ui','sans-serif'],
      display:['Plus Jakarta Sans','system-ui','sans-serif'],
      mono:['JetBrains Mono','monospace']
    },
    colors:{surface:'var(--surface)',primary:'var(--text-primary)',muted:'var(--text-muted)',brand:'var(--brand-green)'}
  }}
};
