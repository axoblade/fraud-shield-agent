import "./Landing.css";

interface Props {
	onEnter: () => void;
}

export default function Landing({ onEnter }: Props) {
	return (
		<div className='landing'>
			{/* ── Hero ── */}
			<header className='landing-hero'>
				<div className='hero-badge'>
					Google Cloud Rapid Agent Hackathon · MongoDB Track
				</div>
				<h1>
					FraudShield <span className='hero-accent'>Agent</span>
				</h1>
				<p className='hero-tagline'>
					An autonomous AI agent that investigates and blocks mobile money fraud
					in real time — before the money leaves the account.
				</p>
				<div className='hero-actions'>
					<button className='hero-cta' onClick={onEnter}>
						Open Dashboard →
					</button>
					<a href='#case-study' className='hero-secondary'>
						View Case Study ↓
					</a>
				</div>
				<div className='hero-stats'>
					<div className='hero-stat'>
						<span className='hero-stat-value'>6.36M</span>
						<span className='hero-stat-label'>Transactions analysed</span>
					</div>
					<div className='hero-stat'>
						<span className='hero-stat-value'>8,213</span>
						<span className='hero-stat-label'>Fraud detected</span>
					</div>
					<div className='hero-stat'>
						<span className='hero-stat-value'>&lt;500ms</span>
						<span className='hero-stat-label'>Query time</span>
					</div>
					<div className='hero-stat'>
						<span className='hero-stat-value'>7</span>
						<span className='hero-stat-label'>Investigation tools</span>
					</div>
				</div>
			</header>

			{/* ── Problem ── */}
			<section className='landing-section'>
				<h2>The Problem</h2>
				<p className='section-lead'>
					Mobile money is the financial backbone of Sub-Saharan Africa. It's
					also the fastest-growing target for financial crime.
				</p>
				<div className='section-grid three-col'>
					<div className='stat-card'>
						<span className='stat-value'>800M+</span>
						<span className='stat-label'>
							registered mobile money accounts across Africa
						</span>
					</div>
					<div className='stat-card'>
						<span className='stat-value'>$1B+</span>
						<span className='stat-label'>
							lost annually to mobile money fraud
						</span>
					</div>
					<div className='stat-card'>
						<span className='stat-value'>0.13%</span>
						<span className='stat-label'>
							of transactions are fraudulent — finding them is the challenge
						</span>
					</div>
				</div>
				<div className='problem-narrative'>
					<p>
						Fraudsters exploit the speed of mobile money. They drain accounts
						through rapid cash-outs, route funds through mule networks, and
						manipulate account balances — often before the victim sees a
						notification. Traditional rule-based systems flag transactions hours
						or days later. By then, the money is gone.
					</p>
					<p>
						<strong>FraudShield Agent</strong> investigates every transaction in
						real time. It doesn't just apply rules — it <em>reasons</em> about
						what it finds, decides how deep to dig, and acts before the fraud
						completes.
					</p>
				</div>
			</section>

			{/* ── How It Works ── */}
			<section className='landing-section dark'>
				<h2>How It Works</h2>
				<p className='section-lead'>
					A transaction arrives. The agent investigates. A decision is made —
					all in real time.
				</p>
				<div className='how-it-works'>
					<div className='hw-step'>
						<div className='hw-icon'>
							<svg
								width='24'
								height='24'
								viewBox='0 0 24 24'
								fill='none'
								stroke='currentColor'
								strokeWidth='2'
								strokeLinecap='round'
								strokeLinejoin='round'
							>
								<path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' />
								<polyline points='17 8 12 3 7 8' />
								<line x1='12' y1='3' x2='12' y2='15' />
							</svg>
						</div>
						<div className='hw-connector' />
						<h3>Transaction Arrives</h3>
						<p>
							CASH_OUT, TRANSFER, PAYMENT, or DEBIT hits the platform.
							FraudShield Agent intercepts it instantly via REST API.
						</p>
					</div>
					<div className='hw-step'>
						<div className='hw-icon'>
							<svg
								width='24'
								height='24'
								viewBox='0 0 24 24'
								fill='none'
								stroke='currentColor'
								strokeWidth='2'
								strokeLinecap='round'
								strokeLinejoin='round'
							>
								<circle cx='12' cy='12' r='10' />
								<path d='M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3' />
								<line x1='12' y1='17' x2='12.01' y2='17' />
							</svg>
						</div>
						<div className='hw-connector' />
						<h3>Agent Investigates</h3>
						<p>
							Gemini 2.5 Flash chooses which of 7 tools to call — history,
							velocity, mule, baseline, balance, risk. Up to 6 adaptive turns.
						</p>
					</div>
					<div className='hw-step'>
						<div className='hw-icon'>
							<svg
								width='24'
								height='24'
								viewBox='0 0 24 24'
								fill='none'
								stroke='currentColor'
								strokeWidth='2'
								strokeLinecap='round'
								strokeLinejoin='round'
							>
								<ellipse cx='12' cy='5' rx='9' ry='3' />
								<path d='M21 12c0 1.66-4 3-9 3s-9-1.34-9-3' />
								<path d='M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5' />
							</svg>
						</div>
						<div className='hw-connector' />
						<h3>MongoDB Responds</h3>
						<p>
							6.36M indexed transactions queried via 5 MCP tools. Every query
							returns in under 500ms with compound indexes.
						</p>
					</div>
					<div className='hw-step'>
						<div className='hw-icon'>
							<svg
								width='24'
								height='24'
								viewBox='0 0 24 24'
								fill='none'
								stroke='currentColor'
								strokeWidth='2'
								strokeLinecap='round'
								strokeLinejoin='round'
							>
								<polyline points='20 6 9 17 4 12' />
							</svg>
						</div>
						<h3>Decision &amp; Action</h3>
						<p>
							Risk score 0–100. Block, flag, or allow. Alert logged. SMS
							notification sent. Full investigation trace recorded.
						</p>
					</div>
				</div>
			</section>

			{/* ── Case Study ── */}
			<section className='landing-section' id='case-study'>
				<h2>Case Study: PaySim Fraud Detection</h2>
				<p className='section-lead'>
					We tested FraudShield Agent against the PaySim mobile money simulator
					— the gold standard dataset for mobile financial fraud research.
				</p>

				<div className='case-study-grid'>
					<div className='case-card'>
						<h3>Dataset</h3>
						<ul>
							<li>6,362,620 transactions from a simulated 30-day period</li>
							<li>
								5 transaction types: CASH_OUT, TRANSFER, PAYMENT, DEBIT, CASH_IN
							</li>
							<li>
								8,213 fraudulent transactions (0.13% — realistic class
								imbalance)
							</li>
							<li>Includes agent-to-client and client-to-agent flows</li>
						</ul>
					</div>
					<div className='case-card'>
						<h3>Fraud Patterns Detected</h3>
						<ul>
							<li>
								<strong>Rapid cash-out:</strong> Accounts draining &gt;$500K
								across multiple transactions in a single day
							</li>
							<li>
								<strong>Money mule networks:</strong> TRANSFER chains routing
								funds through intermediary accounts
							</li>
							<li>
								<strong>Balance mismatch:</strong> Transactions where oldBalance
								− amount ≠ newBalance — sign of account manipulation
							</li>
							<li>
								<strong>Velocity spikes:</strong> Sudden bursts of activity from
								previously dormant accounts
							</li>
						</ul>
					</div>
					<div className='case-card'>
						<h3>Agent Performance</h3>
						<ul>
							<li>
								All 4 detection queries return in <strong>under 200ms</strong>{" "}
								on 6.36M documents
							</li>
							<li>
								Compound indexes on nameOrig, type, amount, step, and nameDest
							</li>
							<li>
								Multi-turn reasoning adapts depth: quick check for small
								payments, deep investigation for large cash-outs
							</li>
							<li>
								Heuristic baseline runs alongside every Gemini decision for
								consistency
							</li>
						</ul>
					</div>
					<div className='case-card'>
						<h3>Key Insight</h3>
						<blockquote>
							"Of 6.36M transactions, only 0.13% are fraudulent. A fixed
							pipeline wastes compute on every harmless payment. FraudShield
							Agent adapts — a $50 PAYMENT gets a single history check; a $500K
							CASH_OUT triggers full velocity, mule, baseline, and balance
							investigation. The agent
							<em>chooses</em> how deep to go."
						</blockquote>
					</div>
				</div>
			</section>

			{/* ── Screenshots ── */}
			<section className='landing-section dark'>
				<h2>Screenshots</h2>
				<div className='screenshot-grid'>
					<figure className='screenshot'>
						<img
							src='/images/dashboard.png'
							alt='FraudShield Agent Dashboard — live replay, metrics, and verbose log'
						/>
						<figcaption>
							Live replay dashboard with WebSocket metrics, batched transaction
							results, and verbose terminal log
						</figcaption>
					</figure>
					<figure className='screenshot'>
						<img
							src='/images/single_analysis_evaluation_blocked.png'
							alt='Single transaction analysis — BLOCKED decision with full agent trace'
						/>
						<figcaption>
							Manual transaction evaluation showing a BLOCKED decision with
							complete agent investigation trace
						</figcaption>
					</figure>
				</div>
			</section>

			{/* ── Use Cases ── */}
			<section className='landing-section dark'>
				<h2>Use Cases</h2>
				<div className='use-case-grid'>
					<div className='use-case'>
						<h3>Mobile Network Operators</h3>
						<p>
							M-Pesa, MTN Mobile Money, Airtel Money — any operator running a
							mobile money platform can deploy FraudShield Agent as a real-time
							transaction screening layer. Integrate via REST API. Block fraud
							before the SMS confirmation is sent.
						</p>
					</div>
					<div className='use-case'>
						<h3>Commercial Banks</h3>
						<p>
							Banks offering mobile banking in emerging markets face the same
							fraud patterns. FraudShield plugs into existing transaction
							pipelines and adds an AI reasoning layer on top of conventional
							fraud rules.
						</p>
					</div>
					<div className='use-case'>
						<h3>Fintech &amp; Payment Gateways</h3>
						<p>
							Payment processors handling cross-border remittances or merchant
							payments can use FraudShield to screen for mule accounts and rapid
							cash-out patterns before settlement completes.
						</p>
					</div>
					<div className='use-case'>
						<h3>Regulatory &amp; Compliance</h3>
						<p>
							Central banks and financial intelligence units can run FraudShield
							in batch mode across historical transaction data to identify
							systemic fraud networks and inform policy.
						</p>
					</div>
				</div>
			</section>

			{/* ── Why Different ── */}
			<section className='landing-section'>
				<h2>What Sets It Apart</h2>
				<div className='diff-grid'>
					<div className='diff-card'>
						<h3>Autonomous, not scripted</h3>
						<p>
							Not a rules engine. Not a classification API. An agent that
							chooses tools, interprets results, and decides when it has enough
							evidence to act.
						</p>
					</div>
					<div className='diff-card'>
						<h3>Transparent reasoning</h3>
						<p>
							Every tool call is logged with Gemini's justification. A heuristic
							baseline runs alongside every decision. Nothing is a black box.
						</p>
					</div>
					<div className='diff-card'>
						<h3>Adaptive depth</h3>
						<p>
							Small payments to known accounts get a quick check. Large
							cash-outs to new recipients get full multi-tool investigation. No
							wasted compute.
						</p>
					</div>
					<div className='diff-card'>
						<h3>Production-ready data layer</h3>
						<p>
							6.36M indexed transactions. Compound indexes verified. 5 MCP
							tools. Everything runs on MongoDB Atlas — scales from free tier to
							enterprise.
						</p>
					</div>
					<div className='diff-card'>
						<h3>Real-time dashboard</h3>
						<p>
							Live WebSocket metrics. Transaction replay with speed controls.
							Full agent trace visibility — every tool call, every reasoning
							step, every decision.
						</p>
					</div>
					<div className='diff-card'>
						<h3>Built for hackathon, ready for production</h3>
						<p>
							Docker container. FastAPI + WebSocket backend. React + TypeScript
							frontend. Deploy to Cloud Run in one command. Extend with your own
							SMS provider.
						</p>
					</div>
				</div>
			</section>

			{/* ── Tech ── */}
			<section className='landing-section dark'>
				<h2>Technology Stack</h2>
				<div className='tech-grid'>
					<div className='tech-item'>
						<h4>AI &amp; Reasoning</h4>
						<p>
							Gemini 2.5 Flash · Function Calling · Multi-turn Agent · Heuristic
							Fallback
						</p>
					</div>
					<div className='tech-item'>
						<h4>Database</h4>
						<p>MongoDB Atlas · MCP Protocol · 5 Tools · Compound Indexes</p>
					</div>
					<div className='tech-item'>
						<h4>Backend</h4>
						<p>Python 3.12 · FastAPI · Uvicorn · WebSocket · Loguru</p>
					</div>
					<div className='tech-item'>
						<h4>Frontend</h4>
						<p>
							React 19 · TypeScript · Vite · CSS Custom Properties · Responsive
						</p>
					</div>
					<div className='tech-item'>
						<h4>Deployment</h4>
						<p>Docker · Google Cloud Run · Multi-stage Build</p>
					</div>
					<div className='tech-item'>
						<h4>Data</h4>
						<p>PaySim Dataset · 6.36M Transactions · Chunked Loading</p>
					</div>
				</div>
			</section>

			{/* ── CTA ── */}
			<section className='landing-cta'>
				<h2>See it in action</h2>
				<p>
					Log in with <code>admin</code> / <code>admin</code>. Run a replay.
					Submit a transaction. Watch the agent reason.
				</p>
				<button className='hero-cta' onClick={onEnter}>
					Open Dashboard →
				</button>
			</section>

			<footer className='landing-footer'>
				<p>
					Built by Axoblade · Google Cloud Rapid Agent Hackathon · June 2026
				</p>
				<p className='footer-meta'>
					MongoDB Track · PaySim Dataset · Gemini 2.5 Flash
				</p>
			</footer>
		</div>
	);
}
