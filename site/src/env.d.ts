/// <reference types="astro/client" />

type Runtime = import('@astrojs/cloudflare').Runtime<
  import('./lib/env').OdusiteEnv
>;

declare namespace App {
  interface Locals extends Runtime {
    lang: string;
    locale: string;
    user: { id: number; name: string; email: string } | null;
  }
}

declare module 'virtual:odusite/config' {
  interface NavItem {
    label: string;
    href: string;
    block?: string;
  }
  const config: {
    blocks: Record<string, boolean>;
    theme: string;
    nav: NavItem[];
  };
  export default config;
}
