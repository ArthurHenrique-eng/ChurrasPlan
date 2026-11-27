// Ponto de entrada da Neon Function `selarrt`. A lógica e os testes ficam em
// selarrt-handler.ts; aqui só se lê a configuração do ambiente da Function.
import { criarHandlerSelarrt } from "./selarrt-handler.ts";

const handler = criarHandlerSelarrt({
  seloSegredo: process.env.REALTIME_SELO_SEGREDO,
  realtimeSecret: process.env.NEON_REALTIME_SECRET,
  db: process.env.NEON_REALTIME_DB || "neondb",
});

export default handler;
