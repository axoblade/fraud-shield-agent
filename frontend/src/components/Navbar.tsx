interface Props {
	onLogout: () => void;
	onAnalyze: () => void;
}

export default function Navbar({ onLogout, onAnalyze }: Props) {
	return (
		<nav className='navbar'>
			<div className='nav-brand'>
				<svg
					className='nav-logo'
					viewBox='0 0 24 24'
					width='24'
					height='24'
					fill='none'
					stroke='currentColor'
					strokeWidth='2'
					strokeLinecap='round'
					strokeLinejoin='round'
				>
					<path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' />
				</svg>
				<span className='nav-title'>FraudShield</span>
				<span className='nav-subtitle'>Agent</span>
			</div>
			<div className='nav-actions'>
				<button className='nav-btn nav-analyze' onClick={onAnalyze}>
					Analyze Transaction
				</button>
				<button className='nav-btn nav-logout' onClick={onLogout}>
					Logout
				</button>
			</div>
		</nav>
	);
}
