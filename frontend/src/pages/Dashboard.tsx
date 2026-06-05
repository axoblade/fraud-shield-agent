import { useEffect, useRef, useState } from "react";
import { evaluateTransaction } from "../api";
import MetricsBar from "../components/MetricsBar";
import Navbar from "../components/Navbar";
import ReplayPanel from "../components/ReplayPanel";
import ResultCard from "../components/ResultCard";
import TransactionForm from "../components/TransactionForm";

interface Props {
	onLogout: () => void;
}

interface Metrics {
	total_transactions: number;
	fraud_count: number;
	alerts_count: number;
}

export default function Dashboard({ onLogout }: Props) {
	const [metrics, setMetrics] = useState<Metrics>({
		total_transactions: 0,
		fraud_count: 0,
		alerts_count: 0,
	});
	const [result, setResult] = useState<any>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");
	const [modalOpen, setModalOpen] = useState(false);
	const metricsWs = useRef<WebSocket | null>(null);

	useEffect(() => {
		// Connect to live metrics WebSocket — updates every 5s in real time
		const protocol = location.protocol === "https:" ? "wss:" : "ws:";
		const ws = new WebSocket(`${protocol}//${location.host}/ws/metrics`);
		metricsWs.current = ws;

		ws.onmessage = (e) => {
			const msg = JSON.parse(e.data);
			if (msg.type === "metrics") {
				setMetrics({
					total_transactions: msg.total_transactions,
					fraud_count: msg.fraud_count,
					alerts_count: msg.alerts_count,
				});
			}
		};

		return () => {
			if (metricsWs.current?.readyState === WebSocket.OPEN) {
				metricsWs.current.close();
			}
		};
	}, []);

	const handleEvaluate = async (txn: any) => {
		setLoading(true);
		setError("");
		setResult(null);
		try {
			const r = await evaluateTransaction(txn);
			setResult(r);
		} catch (e: any) {
			setError(e.message);
		} finally {
			setLoading(false);
		}
	};

	return (
		<>
			<Navbar onLogout={onLogout} onAnalyze={() => setModalOpen(true)} />
			<div className='dashboard'>
				<MetricsBar
					total={metrics.total_transactions}
					fraud={metrics.fraud_count}
					alerts={metrics.alerts_count}
				/>
				<ReplayPanel />

				{modalOpen && (
					<div className='modal-overlay' onClick={() => setModalOpen(false)}>
						<div className='modal-panel' onClick={(e) => e.stopPropagation()}>
							<div className='modal-header'>
								<h2>Transaction Analysis</h2>
								<button
									className='modal-close'
									onClick={() => setModalOpen(false)}
								>
									Close
								</button>
							</div>
							<TransactionForm onSubmit={handleEvaluate} loading={loading} />
							{error && (
								<div className='form-error' style={{ marginTop: 10 }}>
									{error}
								</div>
							)}
							{result && <ResultCard {...result} />}
						</div>
					</div>
				)}
			</div>
		</>
	);
}
