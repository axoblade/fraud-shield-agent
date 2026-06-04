interface Props {
  total: number;
  fraud: number;
  alerts: number;
}

export default function MetricsBar({ total, fraud, alerts }: Props) {
  return (
    <div className="metrics-bar">
      <div className="metric-card">
        <div className="value">{total.toLocaleString()}</div>
        <div className="label">Transactions Analyzed</div>
      </div>
      <div className="metric-card">
        <div className="value">{fraud.toLocaleString()}</div>
        <div className="label">Fraudulent</div>
      </div>
      <div className="metric-card">
        <div className="value">{alerts.toLocaleString()}</div>
        <div className="label">Alerts Generated</div>
      </div>
    </div>
  );
}
