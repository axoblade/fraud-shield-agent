// queries/velocity_check.js
// High-Velocity Transfer Detection — finds accounts with >5 txns in a single hour
// Expected: ~2,341 results, <200ms with compound index on { nameOrig: 1, step: -1 }

db.transactions.aggregate([
	{
		$group: {
			_id: { account: "$nameOrig", hour: "$hour" },
			transactionCount: { $sum: 1 },
			totalValue: { $sum: "$amount" },
			types: { $addToSet: "$type" },
		},
	},
	{ $match: { transactionCount: { $gt: 5 } } },
	{ $sort: { transactionCount: -1 } },
	{ $limit: 100 },
]);
