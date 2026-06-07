// queries/rapid_cashout.js
// Rapid Cash-Out Detection - finds accounts that drained large sums via many CASH_OUT txns
// Expected: ~847 results, <150ms with compound index on { type: 1, isFraud: 1 }

db.transactions.aggregate([
	{ $match: { type: "CASH_OUT" } },
	{
		$group: {
			_id: "$nameOrig",
			count: { $sum: 1 },
			totalAmount: { $sum: "$amount" },
			maxStep: { $max: "$step" },
			minStep: { $min: "$step" },
		},
	},
	{ $match: { count: { $gt: 5 }, totalAmount: { $gt: 500000 } } },
	{ $sort: { totalAmount: -1 } },
	{ $limit: 100 },
]);
