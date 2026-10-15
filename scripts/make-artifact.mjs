// Convierte dist-artifact/ (build con VITE_ARTIFACT=1) en un único fragmento HTML para el visor de artefactos.
// Uso: node scripts/make-artifact.mjs <salida.html>
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';

const out = process.argv[2];
if (!out) throw new Error('Indica el archivo de salida');
const dir = new URL('../dist-artifact/assets/', import.meta.url);
const files = readdirSync(dir);
const js = files.filter((f) => f.endsWith('.js'));
const css = files.filter((f) => f.endsWith('.css'));
if (js.length !== 1 || css.length !== 1) throw new Error(`Se esperaba 1 JS y 1 CSS, hay ${js.length} y ${css.length}`);

const safeJs = readFileSync(new URL(js[0], dir), 'utf8').replace(/<\/script/gi, '<\\/script').replace(/<!--/g, '<\\!--');
const safeCss = readFileSync(new URL(css[0], dir), 'utf8').replace(/<\/style/gi, '<\\/style');

writeFileSync(out, `<title>V60 Academy</title>
<style>${safeCss}</style>
<div id="root"></div>
<script type="module">${safeJs}</script>
`);
console.log(`Escrito ${out} (${Math.round((safeJs.length + safeCss.length) / 1024)} KB)`);
