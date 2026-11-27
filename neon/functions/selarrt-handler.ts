/**
 * Function `selarrt`: sela consultas do Neon Realtime pedidas pela API do ChurrasPlan.
 *
 * Quem decide permissão é a API (FastAPI no Render): ela confere a sessão do
 * usuário e se ele pode ver os dados, e só então chama esta Function com uma
 * assinatura HMAC-SHA256 do corpo. Aqui existe apenas uma lista fechada de
 * consultas, com parâmetros inteiros validados. O navegador nunca escolhe SQL;
 * ele recebe a consulta selada (cifrada, válida por cerca de 60 s) e a assina
 * direto no Realtime.
 *
 * O Realtime só oferece SDK em TypeScript para selar consultas, por isso esta
 * parte roda em Node.js nas Neon Functions e não no backend Python.
 */
import { createHmac, timingSafeEqual } from "node:crypto";
import { createRealtime, rawSql } from "@neon/realtime/server";

const TOLERANCIA_SEGUNDOS = 60;
const CORPO_MAXIMO_BYTES = 2048;
const INT4_MAXIMO = 2_147_483_647;

export const CABECALHO_TIMESTAMP = "x-churrasplan-ts";
export const CABECALHO_ASSINATURA = "x-churrasplan-assinatura";

interface DefinicaoConsulta {
  readonly sql: string;
  readonly parametros: readonly string[];
}

/**
 * Consultas que a API pode pedir. Somente leitura e determinísticas, como o
 * Realtime exige. Colunas mínimas: a tela recarrega os valores calculados
 * (preços, totais, progresso) pela API quando algo muda.
 */
export const CONSULTAS: Readonly<Record<string, DefinicaoConsulta>> = Object.freeze({
  lista_compras_itens: Object.freeze({
    sql:
      "SELECT id, comprado, valor_pago_total, comprado_em FROM lista_compras_itens " +
      "WHERE lista_compras_id = $1 ORDER BY id",
    parametros: Object.freeze(["lista_id"]),
  }),
});

export interface OpcoesSelarrt {
  /** Segredo compartilhado com a API (REALTIME_SELO_SEGREDO). */
  readonly seloSegredo: string | undefined;
  /** Segredo do Realtime do branch (NEON_REALTIME_SECRET). */
  readonly realtimeSecret: string | undefined;
  /** Banco do Postgres no Neon. */
  readonly db?: string;
  /** Relógio em segundos Unix; injetável nos testes. */
  readonly agora?: () => number;
}

export function assinar(segredo: string, timestamp: string, corpo: string): string {
  return createHmac("sha256", segredo).update(`${timestamp}.${corpo}`).digest("hex");
}

function resposta(status: number, corpo: unknown): Response {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function assinaturaValida(
  segredo: string,
  timestamp: string,
  assinatura: string,
  corpo: string,
  agora: number,
): boolean {
  if (!/^\d{1,12}$/.test(timestamp) || !/^[0-9a-f]{64}$/.test(assinatura)) return false;
  if (Math.abs(agora - Number(timestamp)) > TOLERANCIA_SEGUNDOS) return false;
  const esperada = Buffer.from(assinar(segredo, timestamp, corpo), "hex");
  return timingSafeEqual(esperada, Buffer.from(assinatura, "hex"));
}

function ehObjetoSimples(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

/** Devolve a definição e os valores na ordem dos placeholders, ou null se inválido. */
export function interpretarPedido(
  dados: unknown,
): { definicao: DefinicaoConsulta; valores: number[] } | null {
  if (!ehObjetoSimples(dados)) return null;
  const nome = dados.consulta;
  const parametros = dados.parametros;
  if (typeof nome !== "string" || !Object.hasOwn(CONSULTAS, nome)) return null;
  if (!ehObjetoSimples(parametros)) return null;
  const definicao = CONSULTAS[nome];
  const chaves = Object.keys(parametros);
  if (chaves.length !== definicao.parametros.length) return null;
  const valores: number[] = [];
  for (const chave of definicao.parametros) {
    const valor = Object.hasOwn(parametros, chave) ? parametros[chave] : undefined;
    if (typeof valor !== "number" || !Number.isInteger(valor) || valor < 1 || valor > INT4_MAXIMO) {
      return null;
    }
    valores.push(valor);
  }
  return { definicao, valores };
}

/**
 * Lê o corpo parando assim que passa do limite, sem confiar no Content-Length
 * (pedidos em chunks não o enviam). Devolve null se o corpo for grande demais.
 */
async function lerCorpoLimitado(request: Request, limite: number): Promise<string | null> {
  if (!request.body) return "";
  const leitor = request.body.getReader();
  const pedacos: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await leitor.read();
    if (done) break;
    total += value.byteLength;
    if (total > limite) {
      await leitor.cancel().catch(() => {});
      return null;
    }
    pedacos.push(value);
  }
  return Buffer.concat(pedacos).toString("utf8");
}

export function criarHandlerSelarrt(opcoes: OpcoesSelarrt) {
  const agora = opcoes.agora ?? (() => Math.floor(Date.now() / 1000));
  let realtime: ReturnType<typeof createRealtime> | null = null;
  if (opcoes.realtimeSecret) {
    try {
      realtime = createRealtime({ secret: opcoes.realtimeSecret, db: opcoes.db ?? "neondb" });
    } catch {
      console.error("selarrt: NEON_REALTIME_SECRET inválido; a Function responde 503.");
    }
  }

  return {
    async fetch(request: Request): Promise<Response> {
      const { pathname } = new URL(request.url);
      if (pathname !== "/selar") return resposta(404, { erro: "rota_inexistente" });
      if (request.method !== "POST") return resposta(405, { erro: "metodo_nao_permitido" });
      if (!opcoes.seloSegredo || !realtime) {
        console.error("selarrt: REALTIME_SELO_SEGREDO ou NEON_REALTIME_SECRET ausente.");
        return resposta(503, { erro: "nao_configurado" });
      }

      const declarado = Number(request.headers.get("content-length") ?? "0");
      if (declarado > CORPO_MAXIMO_BYTES) return resposta(413, { erro: "corpo_grande_demais" });
      const corpo = await lerCorpoLimitado(request, CORPO_MAXIMO_BYTES);
      if (corpo === null) return resposta(413, { erro: "corpo_grande_demais" });

      const timestamp = request.headers.get(CABECALHO_TIMESTAMP) ?? "";
      const assinatura = request.headers.get(CABECALHO_ASSINATURA) ?? "";
      if (!assinaturaValida(opcoes.seloSegredo, timestamp, assinatura, corpo, agora())) {
        return resposta(401, { erro: "assinatura_invalida" });
      }

      let dados: unknown;
      try {
        dados = JSON.parse(corpo);
      } catch {
        return resposta(400, { erro: "json_invalido" });
      }
      const pedido = interpretarPedido(dados);
      if (!pedido) return resposta(400, { erro: "consulta_invalida" });

      const selada = await realtime.seal({ query: rawSql(pedido.definicao.sql, pedido.valores) });
      return resposta(200, selada);
    },
  };
}
