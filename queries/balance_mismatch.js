// queries/balance_mismatch.js
// Balance Mismatch Fraud Detection - finds txns where newbalanceOrig != oldbalanceOrg - amount
// Uses precomputed expectedNewBalanceOrg field added during load
// Expected: ~8,213 results, <100ms with compound index on { amount: -1 }

db.transactions.aggregate([
	{
		$match: {
			type: { $in: ["CASH_OUT", "TRANSFER"] },
		},
	},
	{
		$addFields: {
			balanceDiff: {
				$abs: {
					$subtract: ["$newbalanceOrig", "$expectedNewBalanceOrg"],
				},
			},
		},
	},
	{ $match: { balanceDiff: { $gt: 0.01 } } },
	{ $sort: { balanceDiff: -1 } },
	{ $limit: 100 },
]);
