import { useState } from "react";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  LineChart,
  Line,
} from "recharts";

import "./chatbot.css";

const API_BASE_URL = "http://localhost:8000";

function formatFeatureName(name) {
  const names = {
    previous_abw: "Previous ABW",
    previous_adg: "Previous ADG",
    biomass_kg: "Biomass",
    survival_pct: "Survival",
    temperature_c: "Temperature",
    ph: "pH",
    dissolved_oxygen: "DO",
    salinity_ppt: "Salinity",
    ammonia_mg_l: "Ammonia",
    feed_quantity_kg: "Feed",
    doc: "DOC",
  };

  return names[name] || name;
}

function PredictionCard({ analysis }) {
  if (!analysis || !analysis.prediction) {
    return null;
  }

  const prediction = analysis.prediction;
  const shap = analysis.shap;

  const shapData =
    shap?.explanations?.slice(0, 8).map((item) => ({
      feature: formatFeatureName(item.feature),
      value: Number(item.shap_value),
      impact: item.impact,
    })) || [];

  return (
    <div className="ml-card">
      <div className="ml-card-header">
        <div>
          <div className="ml-label">ML GROWTH PREDICTION</div>

          <h3>{prediction.pond_code}</h3>

          <p>DOC {prediction.doc}</p>
        </div>

        <div className="ai-badge">AI Analysis</div>
      </div>

      <div className="prediction-metrics">
        <div className="prediction-metric">
          <span>Current ABW</span>
          <strong>{prediction.current_abw ?? "--"} g</strong>
        </div>

        <div className="prediction-arrow">→</div>

        <div className="prediction-metric predicted">
          <span>Predicted ABW</span>
          <strong>{prediction.predicted_abw ?? "--"} g</strong>
        </div>

        <div className="prediction-metric">
          <span>Change</span>
          <strong
            className={
              prediction.difference >= 0 ? "positive" : "negative"
            }
          >
            {prediction.difference >= 0 ? "+" : ""}
            {prediction.difference ?? "--"} g
          </strong>
        </div>
      </div>

      {shapData.length > 0 && (
        <div className="shap-section">
          <div className="section-heading">
            <div>
              <h4>SHAP Feature Impact</h4>
              <p>Factors influencing the prediction</p>
            </div>
          </div>

          <div className="shap-chart">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart
                data={shapData}
                layout="vertical"
                margin={{
                  top: 10,
                  right: 20,
                  left: 20,
                  bottom: 10,
                }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  horizontal={false}
                />

                <XAxis type="number" />

                <YAxis
                  dataKey="feature"
                  type="category"
                  width={110}
                />

                <Tooltip
                  formatter={(value) => [value, "SHAP impact"]}
                />

                <Bar dataKey="value" radius={[4, 4, 4, 4]}>
                  {shapData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        entry.impact === "positive"
                          ? "#16a34a"
                          : "#dc2626"
                      }
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="shap-legend">
            <span>
              <i className="positive-dot"></i>
              Positive influence
            </span>

            <span>
              <i className="negative-dot"></i>
              Negative influence
            </span>
          </div>
        </div>
      )}

      {shap?.summary && (
        <div className="ai-explanation">
          <div className="explanation-icon">✦</div>

          <div>
            <strong>AI Explanation</strong>
            <p>{shap.summary}</p>
          </div>
        </div>
      )}

      {prediction.model_metrics && (
        <div className="model-info">
          <div>
            <span>Training rows</span>
            <strong>{prediction.model_metrics.training_rows}</strong>
          </div>

          <div>
            <span>MAE</span>
            <strong>{prediction.model_metrics.mae}</strong>
          </div>

          <div>
            <span>R²</span>
            <strong>{prediction.model_metrics.r2}</strong>
          </div>
        </div>
      )}
    </div>
  );
}

function ChartCard({ chart }) {
  if (!chart || !chart.data) {
    return null;
  }

  const data = chart.data;

  if (chart.chart_type === "multi_line") {
    return (
      <div className="chart-card">
        <h3>{chart.title}</h3>

        <p>Water quality parameters over DOC</p>

        <ResponsiveContainer width="100%" height={330}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />

            <XAxis
              dataKey="doc"
              label={{
                value: "DOC",
                position: "insideBottom",
                offset: -5,
              }}
            />

            <YAxis />

            <Tooltip />

            <Line
              type="monotone"
              dataKey="temperature"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="ph"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="do"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="salinity"
              strokeWidth={2}
              dot={false}
            />

            <Line
              type="monotone"
              dataKey="ammonia"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  if (chart.chart_type === "line") {
    let dataKey = "abw";

    if (
      chart.y_axis &&
      chart.y_axis.toLowerCase().includes("do")
    ) {
      dataKey = "do";
    }

    if (
      chart.y_axis &&
      chart.y_axis.toLowerCase().includes("temperature")
    ) {
      dataKey = "temperature";
    }

    if (
      chart.y_axis &&
      chart.y_axis.toLowerCase().includes("ph")
    ) {
      dataKey = "ph";
    }

    return (
      <div className="chart-card">
        <h3>{chart.title}</h3>

        <p>{chart.y_axis}</p>

        <ResponsiveContainer width="100%" height={330}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />

            <XAxis dataKey="doc" />

            <YAxis />

            <Tooltip />

            <Line
              type="monotone"
              dataKey={dataKey}
              strokeWidth={3}
              dot
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return null;
}

export default function Chatbot() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: "bot",
      text:
        "Hello! I'm AquaLLM. Ask me about your farms, ponds, growth, water quality or predictions.",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  // Keep one conversation ID for this open chatbot so follow-up questions
  // can reuse the previous pond/result context on the backend.
  const [sessionId] = useState(() =>
    (globalThis.crypto && globalThis.crypto.randomUUID)
      ? globalThis.crypto.randomUUID()
      : `aqua-${Date.now()}-${Math.random().toString(36).slice(2)}`
  );

  async function sendMessage(customMessage = null) {
    const question =
      customMessage !== null ? customMessage : input.trim();

    if (!question || loading) {
      return;
    }

    const userMessage = {
      id: Date.now(),
      sender: "user",
      text: question,
    };

    setMessages((previous) => [...previous, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: question,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      const botMessage = {
        id: Date.now() + 1,
        sender: "bot",
        text: data.response || "I couldn't generate a response.",
        type: data.type || "text",
        chart: data.chart || null,
        analysis: data.analysis || null,
      };

      setMessages((previous) => [...previous, botMessage]);
    } catch (error) {
      console.error(error);

      setMessages((previous) => [
        ...previous,
        {
          id: Date.now() + 1,
          sender: "bot",
          text:
            "I couldn't connect to the AquaLLM backend. Make sure FastAPI is running on port 8000.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  }

  const suggestions = [
    "Predict growth of F01-P03",
    "Show ABW trend of F01-P03",
    "Show DO trend of F05-P03",
    "What is the latest ABW of F01-P03?",
  ];

  return (
    <div className="aqua-chat-page">
      <main className="chat-main">
        <header className="chat-header">
          <div>
            <span className="eyebrow">AI FARM ASSISTANT</span>

            <h1>Aquaculture Intelligence</h1>

            <p>
              Ask questions, analyze pond performance,
              visualize trends and predict shrimp growth.
            </p>
          </div>

          <div className="header-status">
            <span className="live-dot"></span>
            Live Database
          </div>
        </header>

        <section className="messages-area">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message-row ${message.sender}`}
            >
              {message.sender === "bot" && (
                <div className="avatar">🦐</div>
              )}

              <div className="message-content">
                <div className="message-bubble">
                  {message.text}
                </div>

                {message.type === "ml_prediction" &&
                  message.analysis && (
                    <PredictionCard analysis={message.analysis} />
                  )}

                {message.type === "chart" &&
                  message.chart && (
                    <ChartCard chart={message.chart} />
                  )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row bot">
              <div className="avatar">🦐</div>

              <div className="typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
        </section>

        <div className="suggestions">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => sendMessage(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>

        <div className="input-wrapper">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about a pond, growth, water quality or prediction..."
            rows={1}
          />

          <button
            className="send-button"
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
          >
            ↑
          </button>
        </div>

        <div className="input-footer">
          AquaLLM can analyze farm data,
          generate charts and explain ML predictions.
        </div>
      </main>
    </div>
  );
}