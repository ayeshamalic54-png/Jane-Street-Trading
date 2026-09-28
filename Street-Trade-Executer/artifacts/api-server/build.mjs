import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build as esbuild } from "esbuild";
import { rm } from "node:fs/promises";

globalThis.require = createRequire(import.meta.url);

const artifactDir = path.dirname(fileURLToPath(import.meta.url));

async function buildAll() {
  const distDir = path.resolve(artifactDir, "dist");
  await rm(distDir, { recursive: true, force: true });

  let plugins = [];
  try {
    const pinoPluginModule = await import("esbuild-plugin-pino");
    const esbuildPluginPino = pinoPluginModule.default || pinoPluginModule;
    if (typeof esbuildPluginPino === "function") {
      plugins.push(esbuildPluginPino({ transports: ["pino-pretty"] }));
    }
  } catch (e) {
    console.warn("esbuild-plugin-pino skipped:", e);
  }

  await esbuild({
    entryPoints: [path.resolve(artifactDir, "src/index.ts")],
    platform: "node",
    bundle: true,
    format: "esm",
    outdir: distDir,
    outExtension: { ".js": ".mjs" },
    logLevel: "info",
    external: [
      "*.node",
      "sharp",
      "better-sqlite3",
      "sqlite3",
      "bcrypt",
      "bufferutil",
      "utf-8-validate",
      "pg-native"
    ],
    sourcemap: "linked",
    plugins,
    banner: {
      js: `import { createRequire as __bannerCrReq } from 'node:module';
import __bannerPath from 'node:path';
import __bannerUrl from 'node:url';

globalThis.require = __bannerCrReq(import.meta.url);
globalThis.__filename = __bannerUrl.fileURLToPath(import.meta.url);
globalThis.__dirname = __bannerPath.dirname(globalThis.__filename);
`,
    },
  });
}

buildAll().catch((err) => {
  console.error("BUILD_ERROR_STACK:", err);
  process.exit(1);
});
