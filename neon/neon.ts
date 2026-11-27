import { defineConfig } from "@neon/config/v1";

/**
 * Serviços do Neon usados pelo ChurrasPlan (projeto `restless-union-65574984`).
 *
 * Aplicar com `neon deploy` a partir desta pasta, sempre primeiro num branch de
 * testes (`neon checkout dev --create`). O branch `production` só recebe
 * `neon deploy` com autorização do proprietário. Detalhes em
 * docs/ChurrasPlanSaaS.md, seção "Serviços do Neon".
 */
export default defineConfig({
  // Já provisionados no branch production pelo console do Neon. Ficam
  // declarados para que `neon deploy` não os desligue e para que
  // `neon env pull` traga NEON_AUTH_* e NEON_AI_GATEWAY_*. O uso no código
  // depende de decisões em aberto (login e orçamento de IA).
  auth: true,
  aiGateway: true,

  preview: {
    // Mudar a lista de origens num branch que já tem Realtime exige
    // `neon deploy --update-existing`.
    realtime: { allowedOrigins: ["https://churrasplan.vercel.app"] },
  },

  functions: {
    selarrt: {
      name: "ChurrasPlan: selar consultas do Realtime",
      source: "./functions/selarrt.ts",
      env: {
        REALTIME_SELO_SEGREDO: { value: process.env.REALTIME_SELO_SEGREDO, required: true },
        NEON_REALTIME_SECRET: { value: process.env.NEON_REALTIME_SECRET, required: true },
      },
    },
  },

  branch: (branch) => {
    if (branch.isDefault) return {};
    if (!branch.exists) return { ttl: "7d" };
    return {};
  },
});
