import { useState, type FormEvent } from "react";

const TYPES = ["CASH_OUT", "TRANSFER", "PAYMENT", "CASH_IN", "DEBIT"];

interface Props {
	onSubmit: (txn: {
		step: number;
		type: string;
		amount: number;
		nameOrig: string;
		nameDest: string;
		oldbalanceOrg: number;
		newbalanceOrig: number;
	}) => Promise<void>;
	loading: boolean;
}

export default function TransactionForm({ onSubmit, loading }: Props) {
	const [day, setDay] = useState(21);
	const [type, setType] = useState("CASH_OUT");
	const [amount, setAmount] = useState("5000");
	const [nameOrig, setNameOrig] = useState("C1231006815");
	const [nameDest, setNameDest] = useState("M1979787155");
	const [oldBalance, setOldBalance] = useState("10000");
	const [errors, setErrors] = useState<string[]>([]);

	const validate = (): string[] => {
		const e: string[] = [];
		if (day < 1 || day > 31) e.push("Day must be 1–31");
		if (!amount || Number(amount) <= 0) e.push("Amount must be > 0");
		if (!nameOrig.trim()) e.push("Origin account required");
		if (!nameDest.trim()) e.push("Destination required");
		if (!oldBalance || Number(oldBalance) < 0)
			e.push("Old balance must be ≥ 0");
		return e;
	};

	const submit = async (e: FormEvent) => {
		e.preventDefault();
		const errs = validate();
		setErrors(errs);
		if (errs.length > 0) return;

		const bal = Number(oldBalance);
		const amt = Number(amount);
		const step = day * 24 - 12; // noon of selected day → balanced 24h window
		await onSubmit({
			step,
			type,
			amount: amt,
			nameOrig: nameOrig.trim(),
			nameDest: nameDest.trim(),
			oldbalanceOrg: bal,
			newbalanceOrig: bal - amt,
		});
	};

	return (
		<form onSubmit={submit}>
			<div className='form-row'>
				<label>
					Type
					<select value={type} onChange={(e) => setType(e.target.value)}>
						{TYPES.map((t) => (
							<option key={t}>{t}</option>
						))}
					</select>
				</label>
				<label>
					Amount ($)
					<input
						type='number'
						min='0.01'
						step='0.01'
						value={amount}
						onChange={(e) => setAmount(e.target.value)}
					/>
				</label>
			</div>
			<div className='form-row'>
				<label>
					Txn Day in the month
					<input
						type='number'
						min={1}
						max={31}
						value={day}
						onChange={(e) => setDay(Number(e.target.value))}
					/>
				</label>
				<label>
					Old Balance ($)
					<input
						type='number'
						min={0}
						step='0.01'
						value={oldBalance}
						onChange={(e) => setOldBalance(e.target.value)}
					/>
				</label>
			</div>
			<div className='form-row'>
				<label>
					Origin Account
					<input
						value={nameOrig}
						onChange={(e) => setNameOrig(e.target.value)}
					/>
				</label>
				<label>
					Destination
					<input
						value={nameDest}
						onChange={(e) => setNameDest(e.target.value)}
					/>
				</label>
			</div>
			{errors.length > 0 && (
				<div className='form-error'>{errors.join(" · ")}</div>
			)}
			<button className='btn-primary' type='submit' disabled={loading}>
				{loading ? "Analyzing..." : "Analyze Transaction"}
			</button>
		</form>
	);
}
