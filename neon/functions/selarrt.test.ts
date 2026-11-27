import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { describe, it } from "node:test";

import {
  CABECALHO_ASSINATURA,
  CABECALHO_TIMESTAMP,
  assinar,
  criarHandlerSelarrt,
} from "./selarrt-handler.ts";

const SEGREDO = "segredo-de-teste-com-32-caracteres!!";
const AGORA = 1_700_000_000;
const realtimeSecret = () => "nrt_live_1" + randomBytes(32).toString("base64url");

function handler(opcoes: Partial<Parameters<typeof criarHandlerSelarrt>[0]> = {}) {
  return criarHandlerSelarrt({
    seloSegredo: SEGREDO,
    realtimeSecret: realtimeSecret(),
    agora: () => AGORA,
    ...opcoes,
  });
}

function pedido(corpo: string, { ts = String(AGORA), assinatura }: { ts?: string; assinatura?: string } = {}) {
  return new Request("https://funcao.exemplo/selar", {
    method: "POST",
    body: corpo,
    headers: {
      "content-type": "application/json",
      [CABECALHO_TIMESTAMP]: ts,
      [CABECALHO_ASSINATURA]: assinatura ?? assinar(SEGREDO, ts, corpo),
    },
  });
}

const corpoLista = (listaId: unknown) =>
  JSON.stringify({ consulta: "lista_compras_itens", parametros: { lista_id: listaId } });

describe("assinatura compartilhada com a API Python", () => {
  it("gera o mesmo HMAC que services/realtime_neon.py (vetor fixo)", () => {
    const corpo = '{"consulta":"lista_compras_itens","parametros":{"lista_id":42}}';
    assert.equal(
      assinar(SEGREDO, "1700000000", corpo),
      "f182f993ce91e7dd5c63ee03df21d47473b3a4c52a07d043deef08e3f308e4b0",
    );
  });
});

describe("selarrt", () => {
  it("sela a consulta da lista de compras", async () => {
    const resposta = await handler().fetch(pedido(corpoLista(42)));
    assert.equal(resposta.status, 200);
    assert.equal(resposta.headers.get("cache-control"), "no-store");
    const selada = await resposta.json();
    assert.equal(typeof selada.capability, "string");
    assert.equal(typeof selada.queryFingerprint, "string");
    assert.ok(selada.expiresAt > Date.now());
    assert.ok(!selada.capability.includes("lista_compras_itens"), "a consulta selada não expõe o SQL");
  });

  it("mesma lista gera a mesma impressão digital; outra lista, outra", async () => {
    const h = handler();
    const a = await (await h.fetch(pedido(corpoLista(7)))).json();
    const b = await (await h.fetch(pedido(corpoLista(7)))).json();
    const c = await (await h.fetch(pedido(corpoLista(8)))).json();
    assert.equal(a.queryFingerprint, b.queryFingerprint);
    assert.notEqual(a.queryFingerprint, c.queryFingerprint);
  });

  it("recusa pedido sem assinatura, com assinatura errada ou de outro segredo", async () => {
    const corpo = corpoLista(1);
    const semAssinatura = new Request("https://funcao.exemplo/selar", { method: "POST", body: corpo });
    assert.equal((await handler().fetch(semAssinatura)).status, 401);
    assert.equal((await handler().fetch(pedido(corpo, { assinatura: "0".repeat(64) }))).status, 401);
    const deOutroSegredo = assinar("outro-segredo", String(AGORA), corpo);
    assert.equal((await handler().fetch(pedido(corpo, { assinatura: deOutroSegredo }))).status, 401);
  });

  it("recusa assinatura válida de um corpo diferente", async () => {
    const assinatura = assinar(SEGREDO, String(AGORA), corpoLista(1));
    assert.equal((await handler().fetch(pedido(corpoLista(2), { assinatura }))).status, 401);
  });

  it("recusa timestamp fora da janela de 60 s", async () => {
    for (const ts of [String(AGORA - 61), String(AGORA + 61), "abc", ""]) {
      const resposta = await handler().fetch(pedido(corpoLista(1), { ts }));
      assert.equal(resposta.status, 401, `ts=${ts}`);
    }
    assert.equal((await handler().fetch(pedido(corpoLista(1), { ts: String(AGORA - 60) }))).status, 200);
  });

  it("recusa consultas e parâmetros fora da lista fechada", async () => {
    const invalidos = [
      JSON.stringify({ consulta: "usuarios", parametros: { lista_id: 1 } }),
      JSON.stringify({ consulta: "toString", parametros: { lista_id: 1 } }),
      JSON.stringify({ consulta: "__proto__", parametros: { lista_id: 1 } }),
      JSON.stringify({ consulta: "lista_compras_itens", parametros: {} }),
      JSON.stringify({ consulta: "lista_compras_itens", parametros: { lista_id: 1, extra: 2 } }),
      JSON.stringify({ consulta: "lista_compras_itens", parametros: [1] }),
      JSON.stringify({ consulta: "lista_compras_itens", sql: "SELECT * FROM usuarios" }),
      corpoLista("1"),
      corpoLista(1.5),
      corpoLista(0),
      corpoLista(-3),
      corpoLista(2_147_483_648),
      corpoLista(null),
      "[]",
      "null",
    ];
    for (const corpo of invalidos) {
      const resposta = await handler().fetch(pedido(corpo));
      assert.equal(resposta.status, 400, corpo);
    }
    assert.equal((await handler().fetch(pedido("{nao-e-json"))).status, 400);
  });

  it("responde 404 fora de /selar e 405 para outros métodos", async () => {
    assert.equal((await handler().fetch(new Request("https://funcao.exemplo/"))).status, 404);
    assert.equal((await handler().fetch(new Request("https://funcao.exemplo/selar"))).status, 405);
  });

  it("recusa corpo grande demais", async () => {
    const corpo = JSON.stringify({ consulta: "lista_compras_itens", parametros: { lista_id: 1 }, x: "a".repeat(3000) });
    assert.equal((await handler().fetch(pedido(corpo))).status, 413);
  });

  it("para de ler corpo sem Content-Length assim que passa do limite", async () => {
    let pedacosLidos = 0;
    let cancelado = false;
    const corpoSemFim = new ReadableStream<Uint8Array>({
      pull(controle) {
        pedacosLidos += 1;
        if (pedacosLidos > 1000) return controle.close();
        controle.enqueue(new Uint8Array(1024).fill(97));
      },
      cancel() {
        cancelado = true;
      },
    });
    const requisicao = new Request("https://funcao.exemplo/selar", {
      method: "POST",
      body: corpoSemFim,
      duplex: "half",
      headers: { [CABECALHO_TIMESTAMP]: String(AGORA), [CABECALHO_ASSINATURA]: "0".repeat(64) },
    } as RequestInit);
    assert.equal(requisicao.headers.get("content-length"), null);

    assert.equal((await handler().fetch(requisicao)).status, 413);
    assert.ok(pedacosLidos <= 4, `leu ${pedacosLidos} pedaços de 1 KB`);
    assert.ok(cancelado);
  });

  it("responde 503 sem segredos ou com segredo do Realtime inválido", async () => {
    assert.equal((await handler({ seloSegredo: undefined }).fetch(pedido(corpoLista(1)))).status, 503);
    assert.equal((await handler({ realtimeSecret: undefined }).fetch(pedido(corpoLista(1)))).status, 503);
    assert.equal((await handler({ realtimeSecret: "nrt_live_1curto" }).fetch(pedido(corpoLista(1)))).status, 503);
  });
});
