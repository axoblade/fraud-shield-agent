import babel from "@rolldown/plugin-babel";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import { readFileSync } from "fs";
import { defineConfig } from "vite";

const version = readFileSync("../VERSION", "utf-8").trim();

export default defineConfig({
	define: {
		APP_VERSION: JSON.stringify(version),
	},
	plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
	server: {
		proxy: {
			"/api": "http://localhost:8000",
			"/ws": {
				target: "ws://localhost:8000",
				ws: true,
			},
		},
	},
});
