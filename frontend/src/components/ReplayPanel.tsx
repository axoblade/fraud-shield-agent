import { useCallback, useRef, useState } from "react";
import { createReplaySocket } from "../api";

interface ReplayRow {
	index: number;
	total: number;
	transaction: {
		step: number;
		type: string;
		amount: number;
		nameOrig: string;
		nameDest: string;
	};
	risk_score: number;
	action: string;
	reasoning: string;
	key_signals: string[];
	elapsed_ms: number;
	alert_id: string;
}

function badge(action: string): string {
	return action === "block" ? "block" : action === "flag" ? "flag" : "allow";
}
function actionLabel(action: string): string {
	return action === "block"
		? "BLOCKED"
		: action === "flag"
			? "FLAGGED"
			: "ALLOWED";
}

export default function ReplayPanel() {
	const [running, setRunning] = useState(false);
	const [rows, setRows] = useState<ReplayRow[]>([]);
	const [logs, setLogs] = useState<string[]>([]);
	const [progress, setProgress] = useState("");
	const [limit, setLimit] = useState(100);
	const [speed, setSpeed] = useState(5);
	const wsRef = useRef<WebSocket | null>(null);

	const addLog = (msg: string) => setLogs((prev) => [...prev.slice(-500), msg]);

	const start = useCallback(() => {
		setRows([]);
		setLogs([]);
		setRunning(true);
		const ws = createReplaySocket();
		wsRef.current = ws;
		ws.onopen = () => {
			addLog(
				`[WS] Connected. Replay starting: ${limit} txns at ${speed}× speed`,
			);
			ws.send(JSON.stringify({ action: "start", limit, speed }));
		};
		ws.onmessage = (e) => {
			const msg = JSON.parse(e.data);
			if (msg.type === "replay_start") {
				addLog(
					`[INIT]  Fetched ${msg.total} transactions (${msg.fraud} fraud + ${msg.normal} normal)`,
				);
				setProgress(`0 / ${msg.total}`);
			} else if (msg.type === "transaction_result") {
				setRows((prev) => [msg as ReplayRow, ...prev]);
				const t = msg.transaction;
				addLog(
					`[${String(msg.index).padStart(3, "0")}/${msg.total}] ${t.type.padEnd(9)} $${t.amount.toLocaleString().padStart(12)} | ${t.nameOrig} → ${t.nameDest} | score=${msg.risk_score} ${msg.action.toUpperCase()} | ${msg.elapsed_ms}ms`,
				);
				setProgress(`${msg.index} / ${msg.total}`);
			} else if (msg.type === "replay_complete") {
				addLog(`[DONE]  ✅ All ${msg.total} transactions processed`);
				setRunning(false);
				setProgress(`Complete — ${msg.total} txns`);
			} else if (msg.type === "replay_stopped") {
				addLog("[STOP]  ⏹ Replay stopped by user");
				setRunning(false);
			} else if (msg.type === "error") {
				addLog(`[ERROR] ${msg.error}`);
			}
		};
		ws.onclose = () => {
			if (ws === wsRef.current) {
				addLog("[WS]    Disconnected");
				setRunning(false);
			}
		};
		ws.onerror = () => {
			if (ws === wsRef.current) {
				addLog("[WS]    Connection error");
				setRunning(false);
			}
		};
	}, [limit, speed]);

	const stop = useCallback(() => {
		const ws = wsRef.current;
		if (!ws || ws.readyState !== WebSocket.OPEN) {
			setRunning(false);
			addLog("[STOP]  Connection already closed");
			return;
		}
		ws.send(JSON.stringify({ action: "stop" }));
		// Give server a moment to process the stop before we close
		setTimeout(() => {
			if (ws.readyState === WebSocket.OPEN) ws.close();
			setRunning(false);
		}, 500);
	}, []);

	return (
		<div className='replay-full'>
			<div className='replay-controls'>
				<button className='btn-start' onClick={start} disabled={running}>
					Start Replay
				</button>
				<button className='btn-stop' onClick={stop} disabled={!running}>
					Stop
				</button>
				<span className='control-group'>
					Limit
					<select
						value={limit}
						onChange={(e) => setLimit(Number(e.target.value))}
					>
						<option value={50}>50</option>
						<option value={100}>100</option>
						<option value={200}>200</option>
						<option value={500}>500</option>
					</select>
				</span>
				<span className='control-group'>
					Speed
					<select
						value={speed}
						onChange={(e) => setSpeed(Number(e.target.value))}
					>
						<option value={1}>1×</option>
						<option value={5}>5×</option>
						<option value={10}>10×</option>
						<option value={20}>20×</option>
					</select>
				</span>
				{progress && <span className='replay-progress-inline'>{progress}</span>}
			</div>

			<div className='replay-split'>
				<div className='replay-results'>
					<h3>Results & Reasoning</h3>
					{rows.length === 0 && !running && (
						<div className='empty-state'>Press Start Replay to begin</div>
					)}
					{rows.map((r, i) => (
						<div
							key={i}
							className={`result-card ${badge(r.action)}`}
							style={{ marginTop: i === 0 ? 0 : 8 }}
						>
							<h3>
								{actionLabel(r.action)} &mdash; Risk: {r.risk_score}/100
							</h3>
							<div className='result-meta'>
								<span>{r.transaction.type}</span>
								<span>${r.transaction.amount.toLocaleString()}</span>
								<span>
									{r.transaction.nameOrig} → {r.transaction.nameDest}
								</span>
								<span className='ms'>{r.elapsed_ms}ms</span>
							</div>
							<p className='reasoning'>{r.reasoning}</p>
							<div className='signals'>
								{r.key_signals.map((s) => (
									<span key={s} className='tag'>
										{s}
									</span>
								))}
							</div>
						</div>
					))}
				</div>
				<div className='replay-log'>
					<h3>Verbose Log</h3>
					<div className='terminal'>
						{logs.length === 0 && !running && (
							<div className='empty-state'>
								Log output appears here during replay
							</div>
						)}
						{logs.map((l, i) => (
							<div key={i} className='log-line'>
								{l}
							</div>
						))}
					</div>
				</div>
			</div>
		</div>
	);
}
