interface Props {
	risk_score: number;
	risk_level: string;
	action: string;
	reasoning: string;
	key_signals: string[];
	elapsed_ms: number;
	trace?: {
		turn: number;
		tool: string;
		args: Record<string, any>;
		result_summary: string;
		elapsed_ms: number;
	}[];
}

function badge(action: string): { label: string; css: string } {
	if (action === "block") return { label: "Blocked", css: "block" };
	if (action === "flag") return { label: "Flagged", css: "flag" };
	return { label: "Allowed", css: "allow" };
}

const TOOL_LABELS: Record<string, string> = {
	fetch_account_history: "History",
	calculate_velocity: "Velocity",
	check_mule_status: "Mule Check",
	get_baseline: "Baseline",
	check_risk_history: "Risk History",
	check_balance_mismatch: "Balance",
};

export default function ResultCard(r: Props) {
	const { label, css } = badge(r.action);
	return (
		<div className={`result-card ${css}`}>
			<h3>
				{label} &mdash; Risk Score: {r.risk_score}/100
			</h3>
			<p className='elapsed'>Evaluated in {r.elapsed_ms}ms</p>
			<p className='reasoning'>{r.reasoning}</p>
			<div className='signals'>
				{r.key_signals.map((s) => (
					<span key={s} className='tag'>
						{s}
					</span>
				))}
			</div>
			{r.trace && r.trace.length > 0 && (
				<div className='agent-trace'>
					<div className='trace-header'>Agent Investigation</div>
					{r.trace.map((t, i) => (
						<div key={i} className='trace-step'>
							<span className='trace-turn'>T{t.turn}</span>
							<span className='trace-tool'>
								{TOOL_LABELS[t.tool] || t.tool}
							</span>
							<span className='trace-result'>{t.result_summary}</span>
							<span className='trace-ms'>{t.elapsed_ms}ms</span>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
