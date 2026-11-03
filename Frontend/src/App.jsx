import { useState } from "react";
import Dashboard from "./dashboard";
import WeeklyFeedForecast from "./WeeklyFeedForecast";
import DataUpload from "./Data Upload";
import Chatbot from "./Chatbot";
import "./App.css";

const menuItems = [
  { label: "Dashboard", icon: "▦" },
  { label: "Analytics & Forecasts", icon: "📈" },
  { label: "Upload Data", icon: "⬆️" },
  { label: "AquaLLM Chatbot", icon: "💬" },
];

export default function App() {
  const [activeMenu, setActiveMenu] = useState("Dashboard");

  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="app-brand-icon">🦐</span>
          <div>
            <h2>AquaLLM</h2>
            <small>Aquaculture Intelligence</small>
          </div>
        </div>

        <nav className="app-navigation">
          {menuItems.map((item) => (
            <button
              key={item.label}
              type="button"
              className={
                activeMenu === item.label
                  ? "app-nav-item active"
                  : "app-nav-item"
              }
              onClick={() => setActiveMenu(item.label)}
            >
              <span>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <section className="app-main">
        <header className="app-topbar">
          <h1>{activeMenu}</h1>
        </header>

        <div className="app-page">
          {activeMenu === "Dashboard" && <Dashboard />}

          {activeMenu === "Analytics & Forecasts" && (
            <WeeklyFeedForecast />
          )}

          {activeMenu === "Upload Data" && <DataUpload />}

          {activeMenu === "AquaLLM Chatbot" && <Chatbot />}
        </div>
      </section>
    </div>
  );
}