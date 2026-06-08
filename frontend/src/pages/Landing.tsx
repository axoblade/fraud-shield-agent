import "./Landing.css";

interface Props {
	onEnter: () => void;
}

export default function Landing({ onEnter }: Props) {
	const proofMetrics = [
		{ value: "6.36M", label: "Transactions Indexed" },
		{ value: "8,213", label: "Fraud Labels" },
		{ value: "0.13%", label: "Fraud Rate" },
		{ value: "<200ms", label: "Query Latency" },
	];

	const pipeline = [
		{
			step: "01",
			title: "Transaction Intake",
			description:
				"FastAPI receives PAYMENT, TRANSFER, CASH_OUT, DEBIT, and CASH_IN events in real time and normalizes payloads for the agent.",
		},
		{
			step: "02",
			title: "Adaptive Reasoning",
			description:
				"Gemini 2.5 Flash with Google ADK function tools starts with history, then expands into deeper checks only when risk evidence emerges.",
		},
		{
			step: "03",
			title: "MongoDB MCP Evidence",
			description:
				"MongoDB Atlas and MCP tools run indexed find and aggregate pipelines for velocity, mule activity, and balance integrity.",
		},
		{
			step: "04",
			title: "Decision and Action",
			description:
				"Agent returns a 0-100 risk score with explicit ALLOW, FLAG, or BLOCK action, then logs auditable traces for operations teams.",
		},
	];

	return (
		<div className='landing'>
			<header className='landing-hero'>
				<nav className='hero-nav'>
					<div className='hero-badge'>
						Google Cloud Rapid Agent Hackathon 2026
					</div>
					<div className='hero-links'>
						<a href='#problem'>Problem</a>
						<a href='#approach'>Approach</a>
						<a href='#how'>How It Works</a>
						<a href='#proof'>Proof</a>
						<a href='#product'>Product</a>
						<a
							href='https://github.com/axoblade/fraud-shield-agent'
							target='_blank'
							rel='noreferrer'
						>
							GitHub
						</a>
					</div>
				</nav>

				<div className='hero-body'>
					<p className='eyebrow'>AI-Powered Financial Defense</p>
					<h1>
						FraudShield <span>Agent</span>
					</h1>
					<p className='hero-tagline'>
						A real-time fraud investigator for mobile money that reasons,
						chooses tools dynamically, and blocks suspicious transfers before
						value leaves the account.
					</p>
					<div className='hero-actions'>
						<button className='hero-cta' onClick={onEnter}>
							Launch Live Dashboard
						</button>
						<a href='#problem' className='hero-secondary'>
							See how it works
						</a>
					</div>
				</div>

				<div className='hero-metrics'>
					{proofMetrics.map((metric) => (
						<article className='metric-card' key={metric.label}>
							<p className='metric-value'>{metric.value}</p>
							<p className='metric-label'>{metric.label}</p>
						</article>
					))}
				</div>
			</header>

			{/* ── 1. THE PROBLEM ── */}
			<section className='landing-section' id='problem'>
				<div className='section-heading'>
					<p className='section-tag'>The Stakes</p>
					<h2>$1 billion lost annually. Static rules can't keep up.</h2>
				</div>
				<div className='mission-grid'>
					<article className='mission-card'>
						<h3>800M+ mobile money accounts across Africa</h3>
						<p>
							For most users, mobile money isn't a convenience. It's their only
							financial infrastructure. Account drains don't just mean a bad
							week; they mean families can't pay school fees or buy food.
						</p>
					</article>
					<article className='mission-card'>
						<h3>Rules-based systems fail at scale</h3>
						<p>
							Static thresholds generate floods of false positives and still
							miss coordinated attacks. Fraud is almost always detected after
							funds have already moved, sometimes days later.
						</p>
					</article>
					<article className='mission-card'>
						<h3>0.13% fraud rate breaks naive models</h3>
						<p>
							In a dataset of 6.36M transactions, only 8,213 are fraudulent. A
							model that predicts "not fraud" for everything achieves 99.87%
							accuracy and catches zero criminals. This is the accuracy paradox.
						</p>
					</article>
				</div>
			</section>

			{/* ── 2. THE APPROACH ── */}
			<section className='landing-section flow-section' id='approach'>
				<div className='section-heading'>
					<p className='section-tag'>Our Approach</p>
					<h2>An agent that investigates like a human, acts like a machine.</h2>
				</div>
				<div className='mission-grid'>
					<article className='mission-card'>
						<h3>Not a rules engine. Not a classifier.</h3>
						<p>
							FraudShield is an autonomous agent. It chooses which of 7
							investigation tools to call, interprets results, and decides when
							evidence is sufficient to act, up to 6 adaptive turns per
							transaction.
						</p>
					</article>
					<article className='mission-card'>
						<h3>Dynamic investigation depth</h3>
						<p>
							A $50 payment to a known account gets a single history check. A
							$500K cash-out to a new recipient triggers full velocity, mule
							network, baseline, and balance investigation. The agent chooses
							how deep to go.
						</p>
					</article>
					<article className='mission-card'>
						<h3>Transparent by design</h3>
						<p>
							Every tool call is logged with Gemini's reasoning. A heuristic
							baseline runs alongside every decision. Signal tags are
							auto-generated. Nothing is a black box. Reviewers see exactly why
							each decision was made.
						</p>
					</article>
				</div>
			</section>

			{/* ── 3. HOW IT WORKS ── */}
			<section className='landing-section flow-section' id='how'>
				<div className='section-heading'>
					<p className='section-tag'>Architecture</p>
					<h2>Gemini reasons. MongoDB proves. FraudShield acts.</h2>
				</div>

				<div className='flow-grid'>
					{pipeline.map((item) => (
						<article className='flow-card' key={item.step}>
							<span>{item.step}</span>
							<h3>{item.title}</h3>
							<p>{item.description}</p>
						</article>
					))}
				</div>

				<div className='arch-deep'>
					<article className='arch-pillar'>
						<h3 className='arch-pillar-title'>Google Cloud Integration</h3>
						<div className='arch-stack'>
							<div className='arch-layer'>
								<h4>Gemini 2.5 Flash via Google ADK</h4>
								<p>
									The agent's brain. Gemini receives 7 registered investigation tools
									through ADK's FunctionTool API and decides which to call based on
									transaction context. ADK orchestrates the multi-turn loop with
									Agent, Runner, InMemorySessionService, and structured Content/Part
									message formatting built into the framework.
								</p>
							</div>
							<div className='arch-layer'>
								<h4>Function-calling with structured schemas</h4>
								<p>
									Each tool is registered with typed Pydantic parameters. Gemini
									returns protobuf function-call responses that the ADK runtime
									dispatches to Python handlers. A recursive sanitizer strips
									protobuf types before results reach the frontend.
								</p>
							</div>
							<div className='arch-layer'>
								<h4>Cloud Run deployment</h4>
								<p>
									FastAPI backend and React frontend served from a single multi-stage
									Docker container on Cloud Run. Auto-scaling, HTTPS by default, zero
									infrastructure management. Deployed at europe-west1.
								</p>
							</div>
						</div>
					</article>

					<article className='arch-pillar'>
						<h3 className='arch-pillar-title'>MongoDB Integration</h3>
						<div className='arch-stack'>
							<div className='arch-layer'>
								<h4>Atlas M20 with 6.36M indexed documents</h4>
								<p>
									Five compound indexes on nameOrig, type, amount, nameDest, and step
									keep every aggregation pipeline under 200ms even across the full
									dataset. Without indexes the same queries took 8 to 12 seconds.
								</p>
							</div>
							<div className='arch-layer'>
								<h4>MCP Server with 5 database tools</h4>
								<p>
									find, aggregate, count, insert_one, and update_one are exposed
									through the MongoDB MCP server running via npx. The agent calls
									these directly — it does not retrieve raw rows and analyze in
									Python. It delegates analysis to MongoDB's aggregation engine.
								</p>
							</div>
							<div className='arch-layer'>
								<h4>Aggregation pipeline as analytical engine</h4>
								<p>
									Mule network detection uses $lookup to join collections and compare
									inbound vs outbound flows in a single pipeline. Velocity checks use
									$group with time-bucketed $match. The agent chooses which pipeline
									to run based on what the evidence demands.
								</p>
							</div>
						</div>
					</article>
				</div>

				<div className='formula-card'>
					<h3>Risk Decision Policy</h3>
					<p>0-30: Allow | 31-60: Flag for review | 61-100: Block + alert</p>
				</div>
			</section>

			{/* ── 4. PROOF ── */}
			<section className='landing-section' id='proof'>
				<div className='section-heading'>
					<p className='section-tag'>Validation</p>
					<h2>6.36M transactions. Four fraud patterns. One agent.</h2>
				</div>
				<div className='data-grid'>
					<article className='data-card'>
						<h3>Dataset</h3>
						<ul>
							<li>
								6,362,620 PaySim transactions across a 30-day simulation window
							</li>
							<li>8,213 fraud labels at realistic 0.13% prevalence</li>
							<li>
								5 transaction types: CASH_OUT, TRANSFER, PAYMENT, DEBIT, CASH_IN
							</li>
							<li>
								Compound indexes verified on nameOrig, type, amount, nameDest,
								step
							</li>
						</ul>
					</article>
					<article className='data-card'>
						<h3>Fraud patterns caught</h3>
						<ul>
							<li>Rapid cash-out via velocity aggregation over 24h windows</li>
							<li>
								Money mule networks via inbound/outbound flow correlation with
								$lookup
							</li>
							<li>
								Balance mismatch via oldBalance − amount ≠ newBalance integrity
								check
							</li>
							<li>
								Velocity spikes via per-hour anomaly detection from dormant
								accounts
							</li>
						</ul>
					</article>
					<article className='data-card'>
						<h3>Performance</h3>
						<ul>
							<li>
								All 4 detection pipelines run under 200ms on 6.36M documents
							</li>
							<li>
								5 MCP tools: find, aggregate, insert_one, update_one, count
							</li>
							<li>
								Heuristic fallback validates every Gemini decision for
								consistency
							</li>
							<li>
								WebSocket replay engine for realistic evaluation at 1× to 20×
								speed
							</li>
						</ul>
					</article>
				</div>
			</section>

			{/* ── 5. PRODUCT ── */}
			<section className='landing-section screens' id='product'>
				<div className='section-heading'>
					<p className='section-tag'>Live Product</p>
					<h2>See the dashboard. Watch the agent. Trust the decision.</h2>
				</div>
				<div className='screenshot-grid'>
					<figure className='screenshot'>
						<img
							src='/images/dashboard.png'
							alt='FraudShield dashboard with live metrics, transaction replay, and verbose event log'
						/>
						<figcaption>
							Replay cockpit with live KPI counters, batched analysis feed, and
							terminal-style event stream updated over WebSocket.
						</figcaption>
					</figure>
					<figure className='screenshot'>
						<img
							src='/images/single_analysis_evaluation_blocked.png'
							alt='Single transaction analysis with blocked decision and full agent reasoning trace'
						/>
						<figcaption>
							Case review with tool-by-tool reasoning trace, risk signals,
							heuristic baseline, and final action with complete audit trail.
						</figcaption>
					</figure>
				</div>

				<div className='business-grid' style={{ marginTop: 20 }}>
					<article>
						<h3>Mobile Network Operators</h3>
						<p>
							Screen transactions before confirmation SMS. Reduce account-drain
							fraud in real time.
						</p>
					</article>
					<article>
						<h3>Commercial Banks</h3>
						<p>
							Layer intelligent investigation on top of existing anti-fraud
							controls for digital channels.
						</p>
					</article>
					<article>
						<h3>Fintech &amp; Payment Gateways</h3>
						<p>
							Detect mule routing and abnormal transfer bursts before settlement
							finality.
						</p>
					</article>
					<article>
						<h3>Regulatory Analytics</h3>
						<p>
							Replay historical streams and expose coordinated fraud network
							behavior for enforcement.
						</p>
					</article>
				</div>
			</section>

			{/* ── 6. CTA ── */}
			<section className='landing-cta'>
				<div className='cta-body'>
					<p className='section-tag'>One Click Away</p>
					<h2>
						The agent is running. The data is live. The dashboard is ready.
					</h2>
					<p>
						Submit a transaction, watch the investigation unfold tool by tool,
						and see exactly how FraudShield makes every decision in real time.
					</p>
					<div className='cta-actions'>
						<button className='hero-cta' onClick={onEnter}>
							Launch Live Dashboard
						</button>
						<a
							href='https://github.com/axoblade/fraud-shield-agent'
							target='_blank'
							rel='noreferrer'
							className='cta-secondary'
						>
							View on GitHub
						</a>
					</div>
				</div>
			</section>

			<footer className='landing-footer'>
				<p>
					Built by Axoblade for the Google Cloud Rapid Agent Hackathon - June
					2026
				</p>
				<p className='footer-meta'>
					MongoDB Track | Gemini 2.5 Flash | ADK | PaySim | v
					{typeof APP_VERSION !== "undefined" ? APP_VERSION : "1.0.0"}
				</p>
			</footer>
		</div>
	);
}
