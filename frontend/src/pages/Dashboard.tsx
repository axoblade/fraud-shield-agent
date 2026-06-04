import { useEffect, useState } from "react";
import { evaluateTransaction, fetchMetrics } from "../api";
import MetricsBar from "../components/MetricsBar";
import Navbar from "../components/Navbar";
import ReplayPanel from "../components/ReplayPanel";
import ResultCard from "../components/ResultCard";
import TransactionForm from "../components/TransactionForm";

interface Props {
	onLogout: () => void;
}

export default function Dashboard({ onLogout }: Props) {
	const [metrics, setMetrics] = useState({
		total_transactions: 0,
		fraud_count: 0,
		alerts_count: 0,
	});
	const [result, setResult] = useState<any>(null);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");
	const [modalOpen, setModalOpen] = useState(false);

	useEffect(() => {
		fetchMetrics().then(setMetrics).catch(console.error);
	}, [result]);

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
