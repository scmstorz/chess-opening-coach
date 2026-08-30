import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("server-renders the chess coach product shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Chess Opening Coach<\/title>/i);
  assert.match(html, /favicon\.svg/);
  assert.match(html, />Eröffnungen<\/h1>/);
  assert.match(html, /Interaktives Schachbrett/);
  assert.doesNotMatch(html, /Das Brett ist noch nicht aktiv/);
  assert.doesNotMatch(html, /♙/);
  assert.doesNotMatch(html, /Training starten/);
  assert.match(html, /Zug vorschlagen/);
  assert.match(html, /Neue Partie/);
  assert.match(html, /Frage zur Stellung/);
  assert.match(html, /Geerdet mit Stellung, Eröffnungstheorie und Stockfish/);
  assert.doesNotMatch(html, /Freie Rückfragen folgen/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape|SkeletonPreview/);
});
