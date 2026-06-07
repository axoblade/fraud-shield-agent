interface Props {
	total: number;
	fraud: number;
	alerts: number;
	loading?: boolean;
}

export default function MetricsBar({ total, fraud, alerts, loading }: Props) {
	return (
		<div className='metrics-bar'>
			<div className='metric-card'>
				<div className={`value${loading ? " skeleton" : ""}`}>
					{loading ? "···" : total.toLocaleString()}
				</div>
				<div className='label'>Transactions Analyzed</div>
			</div>
			<div className='metric-card'>
				<div className={`value${loading ? " skeleton" : ""}`}>
					{loading ? "···" : fraud.toLocaleString()}
				</div>
				<div className='label'>Fraudulent</div>
			</div>
			<div className='metric-card'>
				<div className={`value${loading ? " skeleton" : ""}`}>
					{loading ? "···" : alerts.toLocaleString()}
				</div>
				<div className='label'>Alerts Generated</div>
			</div>
		</div>
	);
}
