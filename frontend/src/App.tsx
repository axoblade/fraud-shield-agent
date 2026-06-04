import { useState } from "react";
import { clearToken, getToken } from "./api";
import "./App.css";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";

export default function App() {
	const [loggedIn, setLoggedIn] = useState(!!getToken());

	if (!loggedIn) return <Login onLogin={() => setLoggedIn(true)} />;
	return (
		<Dashboard
			onLogout={() => {
				clearToken();
				setLoggedIn(false);
			}}
		/>
	);
}
