// Monta, a partir de core/, a extensão do Chrome (pasta e .zip), o userscript e o caderno.html em dist/.
// Sem dependências: o PNG dos ícones e o .zip são escritos aqui com o zlib do node.
// Uso: node scripts/build.mjs [--ponte]   (--ponte inclui o bridge.js para o caderno.html em file://)
import { readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateSync, deflateRawSync } from 'node:zlib';

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(RAIZ, 'dist');
const EXTENSAO = join(DIST, 'extensao-chrome');
const COM_PONTE = process.argv.includes('--ponte');
const VERSAO = JSON.parse(ler('package.json')).version;
const RAIZ_DO_MODULO = "(typeof globalThis !== 'undefined' ? globalThis : this)";

function ler(relativo) {
  return readFileSync(join(RAIZ, relativo), 'utf8');
}

function modulo(nome) {
  const fonte = ler(`core/${nome}.js`);
  if (!fonte.includes(RAIZ_DO_MODULO)) throw new Error(`core/${nome}.js sem a raiz esperada`);
  return fonte.replace(RAIZ_DO_MODULO, '(escopo)');
}

// Um IIFE por arquivo: nada vaza para o window da página.
function pacote(modulos, cola, escopo = '{}') {
  const partes = modulos.map(modulo).join('\n');
  return `(function () {\n'use strict';\nconst escopo = ${escopo};\n${partes}\n${cola}\n})();\n`;
}

const TABELA_CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buffer) {
  let c = 0xffffffff;
  for (const byte of buffer) c = TABELA_CRC[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function blocoPng(tipo, dados) {
  const tamanho = Buffer.alloc(4);
  tamanho.writeUInt32BE(dados.length);
  const corpo = Buffer.concat([Buffer.from(tipo, 'ascii'), dados]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(corpo));
  return Buffer.concat([tamanho, corpo, crc]);
}

// Quadrado vermelho de cantos arredondados com um X branco.
function icone(lado) {
  const linhas = [];
  const raio = lado * 0.18;
  const espessura = lado * 0.11;
  for (let y = 0; y < lado; y++) {
    const linha = [0];
    for (let x = 0; x < lado; x++) {
      const cx = Math.min(Math.max(x, raio), lado - 1 - raio);
      const cy = Math.min(Math.max(y, raio), lado - 1 - raio);
      const dentro = Math.hypot(x - cx, y - cy) <= raio;
      const margem = lado * 0.28;
      const noX =
        x >= margem && x <= lado - 1 - margem && y >= margem && y <= lado - 1 - margem &&
        (Math.abs(x - y) <= espessura || Math.abs(x + y - (lado - 1)) <= espessura);
      const cor = !dentro ? [0, 0, 0, 0] : noX ? [255, 255, 255, 255] : [180, 35, 24, 255];
      linha.push(...cor);
    }
    linhas.push(Buffer.from(linha));
  }
  const cabecalho = Buffer.alloc(13);
  cabecalho.writeUInt32BE(lado, 0);
  cabecalho.writeUInt32BE(lado, 4);
  cabecalho.set([8, 6, 0, 0, 0], 8);
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    blocoPng('IHDR', cabecalho),
    blocoPng('IDAT', deflateSync(Buffer.concat(linhas))),
    blocoPng('IEND', Buffer.alloc(0)),
  ]);
}

function zip(arquivos) {
  const locais = [];
  const centrais = [];
  let deslocamento = 0;
  const hora = (12 << 11) >>> 0;
  const data = (((2026 - 1980) << 9) | (1 << 5) | 1) >>> 0;
  for (const [nome, conteudo] of arquivos) {
    const dados = Buffer.isBuffer(conteudo) ? conteudo : Buffer.from(conteudo);
    const comprimido = deflateRawSync(dados);
    const nomeBytes = Buffer.from(nome, 'utf8');
    const crc = crc32(dados);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x0800, 6);
    local.writeUInt16LE(8, 8);
    local.writeUInt16LE(hora, 10);
    local.writeUInt16LE(data, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(comprimido.length, 18);
    local.writeUInt32LE(dados.length, 22);
    local.writeUInt16LE(nomeBytes.length, 26);
    locais.push(local, nomeBytes, comprimido);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0800, 8);
    central.writeUInt16LE(8, 10);
    central.writeUInt16LE(hora, 12);
    central.writeUInt16LE(data, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(comprimido.length, 20);
    central.writeUInt32LE(dados.length, 24);
    central.writeUInt16LE(nomeBytes.length, 28);
    central.writeUInt32LE(deslocamento, 42);
    centrais.push(central, nomeBytes);
    deslocamento += local.length + nomeBytes.length + comprimido.length;
  }
  const diretorio = Buffer.concat(centrais);
  const fim = Buffer.alloc(22);
  fim.writeUInt32LE(0x06054b50, 0);
  fim.writeUInt16LE(arquivos.length, 8);
  fim.writeUInt16LE(arquivos.length, 10);
  fim.writeUInt32LE(diretorio.length, 12);
  fim.writeUInt32LE(deslocamento, 16);
  return Buffer.concat([...locais, diretorio, fim]);
}

function manifesto() {
  const m = JSON.parse(ler('extensao-chrome/manifest.json'));
  m.version = VERSAO;
  if (COM_PONTE) {
    m.content_scripts.push({ matches: ['file:///*caderno*.html'], js: ['bridge.js'], run_at: 'document_idle' });
  }
  return JSON.stringify(m, null, 2) + '\n';
}

const arquivosDaExtensao = [
  ['manifest.json', manifesto()],
  ['page.js', pacote(['nucleo', 'tela'], ler('extensao-chrome/page.js'))],
  ['content.js', pacote(['nucleo', 'tela', 'coletor'], ler('extensao-chrome/content.js'))],
  ['popup.html', ler('extensao-chrome/popup.html')],
  ['popup.js', pacote(['nucleo', 'coletor'], ler('extensao-chrome/popup.js'))],
  ['icons/48.png', icone(48)],
  ['icons/128.png', icone(128)],
];
if (COM_PONTE) arquivosDaExtensao.push(['bridge.js', pacote(['nucleo'], ler('extensao-chrome/bridge.js'))]);

rmSync(DIST, { recursive: true, force: true });
for (const [nome, conteudo] of arquivosDaExtensao) {
  const destino = join(EXTENSAO, nome);
  mkdirSync(dirname(destino), { recursive: true });
  writeFileSync(destino, conteudo);
}
writeFileSync(join(DIST, `tec-erros-extensao-${VERSAO}.zip`), zip(arquivosDaExtensao));

const cabecalho = ler('userscript/cabecalho.txt').replace('{{VERSAO}}', VERSAO);
writeFileSync(join(DIST, 'tec-erros.user.js'), cabecalho + '\n' + pacote(['nucleo', 'tela', 'coletor'], ler('userscript/tec-erros.js')));

const caderno = ler('caderno/caderno.html');
const marcador = '<!--NUCLEO-->';
if (!caderno.includes(marcador)) throw new Error('caderno/caderno.html sem ' + marcador);
writeFileSync(join(DIST, 'caderno.html'), caderno.replace(marcador, `<script>\n${pacote(['nucleo'], '', 'window')}</script>`));

console.log(`dist/ pronto (versão ${VERSAO}${COM_PONTE ? ', com a ponte' : ''}):`);
console.log('  extensao-chrome/          carregar sem compactação em chrome://extensions');
console.log(`  tec-erros-extensao-${VERSAO}.zip`);
console.log('  tec-erros.user.js         instalar no Violentmonkey');
console.log('  caderno.html              abrir no navegador, também offline no tablet');
