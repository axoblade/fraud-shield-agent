interface Props {
	risk_score: number;
	risk_level: string;
	action: string;
	reasoning: string;
	key_signals: string[];
	elapsed_ms: number;
}

function badge(action: string): { label: string; css: string } {
	if (action === "block") return { label: "Blocked", css: "block" };
	if (action === "flag") return { label: "Flagged", css: "flag" };
	return { label: "Allowed", css: "allow" };
}

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
		</div>
	);
}
