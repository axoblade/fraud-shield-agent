// queries/mule_network.js
// Money Mule Network Detection — finds accounts receiving many TRANSFERs and forwarding them
// Expected: <500ms with compound index on { nameDest: 1, type: 1 }

db.transactions.aggregate([
	{ $match: { type: "TRANSFER" } },
	{
		$group: {
			_id: "$nameDest",
			receivedAmount: { $sum: "$amount" },
			incomingCount: { $sum: 1 },
		},
	},
	{
		$lookup: {
			from: "transactions",
			localField: "_id",
			foreignField: "nameOrig",
			as: "outgoing",
		},
	},
	{
		$addFields: {
			outgoingCount: { $size: "$outgoing" },
			outgoingAmount: { $sum: "$outgoing.amount" },
		},
	},
	{
		$match: {
			incomingCount: { $gt: 10 },
			outgoingCount: { $gt: 0 },
		},
	},
	{ $sort: { receivedAmount: -1 } },
	{ $limit: 50 },
]);
