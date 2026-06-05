import { useState } from "react";
import { clearToken, getToken } from "./api";
import "./App.css";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import Login from "./pages/Login";

export default function App() {
	const [loggedIn, setLoggedIn] = useState(!!getToken());
	const [showLogin, setShowLogin] = useState(false);

	if (loggedIn) {
		return (
			<Dashboard
				onLogout={() => {
					clearToken();
					setLoggedIn(false);
					setShowLogin(false);
				}}
			/>
		);
	}

	if (showLogin) {
		return (
			<Login
				onLogin={() => setLoggedIn(true)}
				onBack={() => setShowLogin(false)}
			/>
		);
	}

	return <Landing onEnter={() => setShowLogin(true)} />;
}
