import { useState } from "react";
import "./App.css";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";

export default function App() {
	const [inDashboard, setInDashboard] = useState(false);

	if (inDashboard) {
		return <Dashboard onLogout={() => setInDashboard(false)} />;
	}

	return <Landing onEnter={() => setInDashboard(true)} />;
}
