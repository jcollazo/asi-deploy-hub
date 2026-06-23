#!/usr/bin/env node
// generate_pptx.js — PPTX con diagramas Mermaid (CJS + mmdc)
"use strict";
const fs = require("fs");
const { execSync } = require("child_process");
const path = require("path");
const pptxgen = require("pptxgenjs");

const NAVY = "12223A", GOLD = "E5BD44", WHITE = "FFFFFF", BG = "F8F9FB", MUTED = "6C757D";

async function main() {
  const md = fs.readFileSync("/opt/data/asi-deploy-hub/docs/ARCHITECTURE_MERMAID.md", "utf-8");
  const titles = [...md.matchAll(/^## (.*?)$/gm)];
  const blocks = [...md.matchAll(/```mermaid\n([\s\S]*?)```/g)];

  const outDir = "/tmp/mermaid_pngs";
  fs.mkdirSync(outDir, { recursive: true });

  const diagrams = [];
  for (let i = 0; i < Math.min(titles.length, blocks.length); i++) {
    const title = titles[i][1].trim();
    const code = blocks[i][1].trim();
    const mmdFile = path.join(outDir, `d${String(i).padStart(2,"0")}.mmd`);
    const pngFile = path.join(outDir, `d${String(i).padStart(2,"0")}.png`);
    fs.writeFileSync(mmdFile, code);
    console.log(`⬇ ${String(i).padStart(2,"0")} ${title}...`);
    try {
      execSync(`mmdc -i "${mmdFile}" -o "${pngFile}" -b white -w 1920 -s 2 -p /tmp/puppeteer-config.json`, { timeout: 60000, stdio: "pipe" });
      if (fs.existsSync(pngFile) && fs.statSync(pngFile).size > 100) {
        console.log(`  ✅ ${Math.round(fs.statSync(pngFile).size/1024)}KB`);
        diagrams.push({ title, png: pngFile });
      } else { console.log("  ⚠️ empty"); }
    } catch (e) {
      console.log(`  ❌ ${(e.stderr||e.message||"").toString().slice(0,80)}`);
    }
  }

  console.log(`\n📊 ${diagrams.length}/${blocks.length} rendered. Building PPTX...`);
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "PRITS — Gobierno de Puerto Rico";
  pres.title = "FBIB Deploy Hub — Arquitectura";

  // Title
  const ts = pres.addSlide();
  ts.background = { color: NAVY };
  ts.addText("FBIB Deploy Hub", { x: 0.8, y: 1.0, w: 8.4, h: 1.2, fontSize: 44, fontFace: "Georgia", color: GOLD, bold: true, margin: 0 });
  ts.addText("Arquitectura del Sistema", { x: 0.8, y: 2.1, w: 8.4, h: 0.7, fontSize: 22, fontFace: "Calibri", color: WHITE, margin: 0 });
  ts.addText("Plataforma de despliegue gubernamental multi-agencia", { x: 0.8, y: 2.8, w: 8.4, h: 0.5, fontSize: 14, fontFace: "Calibri", color: MUTED, margin: 0 });
  ts.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 3.5, w: 1.5, h: 0.04, fill: { color: GOLD } });
  ts.addText("Gobierno de Puerto Rico  ·  Junio 2026  ·  🇵🇷", { x: 0.8, y: 3.8, w: 8.4, h: 0.4, fontSize: 11, fontFace: "Calibri", color: MUTED, margin: 0 });

  // Agenda
  const ag = pres.addSlide();
  ag.background = { color: BG };
  ag.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.95, fill: { color: NAVY } });
  ag.addText("Contenido", { x: 0.6, y: 0.15, w: 8.8, h: 0.65, fontSize: 22, fontFace: "Georgia", color: WHITE, bold: true, margin: 0 });
  ag.addText(diagrams.map((d, i) => ({ text: `${i+1}.  ${d.title}`, options: { fontSize: 15, color: NAVY, breakLine: true, paraSpaceAfter: 8 } })), { x: 1.0, y: 1.3, w: 8, h: 4, valign: "top" });

  // Diagram slides
  for (const d of diagrams) {
    const slide = pres.addSlide();
    slide.background = { color: BG };
    slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.95, fill: { color: NAVY } });
    slide.addText(d.title, { x: 0.6, y: 0.15, w: 8.8, h: 0.65, fontSize: 20, fontFace: "Georgia", color: WHITE, bold: true, margin: 0 });
    slide.addImage({ path: d.png, x: 0.3, y: 1.05, w: 9.4, h: 4.3, sizing: { type: "contain", w: 9.4, h: 4.3 } });
    slide.addText(`PRITS  ·  FBIB Deploy Hub  ·  ${d.title}`, { x: 0.4, y: 5.25, w: 9.2, h: 0.3, fontSize: 8, fontFace: "Calibri", color: MUTED, margin: 0 });
  }

  // Gracias
  const gs = pres.addSlide();
  gs.background = { color: NAVY };
  gs.addText("Gracias", { x: 0.8, y: 1.5, w: 8.4, h: 1.0, fontSize: 40, fontFace: "Georgia", color: GOLD, bold: true, margin: 0 });
  gs.addText("PRITS  ·  Gobierno de Puerto Rico", { x: 0.8, y: 2.6, w: 8.4, h: 0.5, fontSize: 18, fontFace: "Calibri", color: WHITE, margin: 0 });
  gs.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 3.3, w: 1.5, h: 0.04, fill: { color: GOLD } });

  const outPath = "/opt/data/asi-deploy-hub/docs/Arquitectura_FBIB.pptx";
  await pres.writeFile({ fileName: outPath });
  console.log(`\n✅ ${outPath}  (${diagrams.length+3} slides)`);
}

main().catch(e => { console.error(e); process.exit(1); });
