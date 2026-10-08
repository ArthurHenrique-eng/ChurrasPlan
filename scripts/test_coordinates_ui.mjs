import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const forms = [
    { file: "FrontEnd/js/parceiro.js", functionName: "coordenadaFormulario", input: "est-lat", html: "FrontEnd/parceiro.html" },
    { file: "FrontEnd/js/admin.js", functionName: "coordenadaAdmin", input: "admin-est-lat", html: "FrontEnd/admin.html" },
];

for (const item of forms) {
    const campo = { value: "" };
    const sandbox = {
        document: {
            getElementById: (id) => (id === item.input ? campo : { value: "" }),
            addEventListener: () => {},
        },
        console,
    };
    runInNewContext(readFileSync(item.file, "utf8"), sandbox, { filename: item.file });
    const validar = sandbox[item.functionName];
    assert.equal(typeof validar, "function", item.functionName);

    campo.value = "-19,959383";
    assert.equal(validar(item.input, 90), -19.959383);
    assert.equal(campo.value, "-19.959383");

    campo.value = "-19.959383";
    assert.equal(validar(item.input, 90), -19.959383);

    campo.value = "-19959383";
    assert.throws(() => validar(item.input, 90), /fora do intervalo/);
    assert.equal(campo.value, "-19959383", "não converter coordenadas ambíguas");

    campo.value = "91";
    assert.throws(() => validar(item.input, 90), /fora do intervalo/);

    campo.value = "qualquer";
    assert.throws(() => validar(item.input, 90), /Coordenada inválida/);

    campo.value = "";
    assert.equal(validar(item.input, 90), null);

    const html = readFileSync(item.html, "utf8");
    const element = html.match(new RegExp('<input[^>]*id="' + item.input + '"[^>]*>'));
    assert.ok(element, "campo de coordenada visível em " + item.html);
    assert.match(element[0], /type="text"/, "aceitar vírgula decimal em navegadores pt-BR");
    assert.match(element[0], /inputmode="decimal"/);
}

console.log("Formulários de coordenadas: 2 interfaces validadas.");
