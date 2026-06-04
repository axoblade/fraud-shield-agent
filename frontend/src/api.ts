const API_BASE = ""; // Vite proxies /api → backend, /ws → backend

let authToken: string | null = localStorage.getItem("fraudshield_token");

export function getToken(): string | null {
	return authToken;
}

export function setToken(token: string) {
	authToken = token;
	localStorage.setItem("fraudshield_token", token);
}

export function clearToken() {
	authToken = null;
	localStorage.removeItem("fraudshield_token");
}

async function api(path: string, options: RequestInit = {}): Promise<Response> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		...((options.headers as Record<string, string>) || {}),
	};
	if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
	return fetch(`${API_BASE}${path}`, { ...options, headers });
}

async function safeJson(res: Response): Promise<any> {
	const text = await res.text();
	try {
		return JSON.parse(text);
	} catch {
		throw new Error(
			text.slice(0, 200) || `HTTP ${res.status} ${res.statusText}`,
		);
	}
}

export async function login(username: string, password: string) {
	const res = await api("/api/login", {
		method: "POST",
		body: JSON.stringify({ username, password }),
	});
	if (!res.ok) throw new Error("Invalid credentials");
	const data = await safeJson(res);
	setToken(data.token);
	return data;
}

export async function fetchMetrics() {
	const res = await api("/api/metrics");
	return safeJson(res);
}

export async function evaluateTransaction(txn: {
	step: number;
	type: string;
	amount: number;
	nameOrig: string;
	nameDest: string;
	oldbalanceOrg: number;
	newbalanceOrig?: number;
}) {
	const res = await api("/api/evaluate", {
		method: "POST",
		body: JSON.stringify(txn),
	});
	if (!res.ok) {
		const err = await safeJson(res);
		throw new Error(err.detail || err.message || `HTTP ${res.status}`);
	}
	return safeJson(res);
}

export function createReplaySocket(): WebSocket {
	const protocol = location.protocol === "https:" ? "wss:" : "ws:";
	return new WebSocket(`${protocol}//${location.host}/ws/replay`);
}
