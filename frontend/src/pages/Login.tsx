import { useState, type FormEvent } from "react";
import { login } from "../api";

interface Props {
	onLogin: () => void;
	onBack?: () => void;
}

export default function Login({ onLogin, onBack }: Props) {
	const [username, setUsername] = useState("");
	const [password, setPassword] = useState("");
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(false);

	const submit = async (e: FormEvent) => {
		e.preventDefault();
		setError("");
		setLoading(true);
		try {
			await login(username, password);
			onLogin();
		} catch {
			setError("Invalid credentials");
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className='login-page'>
			<form className='login-card' onSubmit={submit}>
				<div className='brand'>
					<svg
						viewBox='0 0 24 24'
						width='28'
						height='28'
						fill='none'
						stroke='currentColor'
						strokeWidth='2'
						strokeLinecap='round'
						strokeLinejoin='round'
					>
						<path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' />
					</svg>
					<h1>FraudShield</h1>
				</div>
				<p className='subtitle'>Agent Dashboard</p>
				<label>
					Username
					<input
						placeholder='admin'
						value={username}
						onChange={(e) => setUsername(e.target.value)}
						autoFocus
					/>
				</label>
				<label>
					Password
					<input
						type='password'
						placeholder='••••••••'
						value={password}
						onChange={(e) => setPassword(e.target.value)}
					/>
				</label>
				{error && <div className='error'>{error}</div>}
				<button className='btn-primary' type='submit' disabled={loading}>
					{loading ? "Signing in…" : "Sign In"}
				</button>
				<p className='hint'>Demo credentials: admin / admin</p>
				{onBack && (
					<button type='button' className='back-link' onClick={onBack}>
						← Back to overview
					</button>
				)}
			</form>
		</div>
	);
}
