import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import "./WeeklyFeedForecast.css";

const API_BASE = "http://127.0.0.1:8000";

export default function WeeklyFeedForecast() {
  const [farms, setFarms] = useState([]);
  const [farmsLoading, setFarmsLoading] = useState(true);
  const [farmId, setFarmId] = useState("");
  const [pondId, setPondId] = useState("");
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedFarm = farms.find((farm) => String(farm.id) === farmId);
  const pondsOfFarm = selectedFarm?.ponds || [];
  const selectedPond = pondsOfFarm.find((pond) => String(pond.id) === pondId);

  async function fetchForecast(selectedFarmId = farmId, selectedPondId = pondId) {
    if (!selectedFarmId || !selectedPondId) {
      setError("Select a farm and a pond.");
      return;
    }

    setLoading(true);
    setError("");
    setForecast(null);

    try {
      const response = await fetch(
        `${API_BASE}/api/feed-prediction/weekly/${Number(selectedFarmId)}/${Number(selectedPondId)}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : JSON.stringify(data.detail || "Unable to load forecast.")
        );
      }

      setForecast(data);
    } catch (err) {
      setError(
        err.message ||
          "Could not connect to AquaLLM API. Check that FastAPI is running."
      );
    } finally {
      setLoading(false);
    }
  }

  // Load farms + ponds from the database once
  useEffect(() => {
    async function loadFarms() {
      setFarmsLoading(true);
      setError("");

      try {
        const response = await fetch(`${API_BASE}/api/feed-prediction/farms`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            typeof data.detail === "string"
              ? data.detail
              : "Unable to load farms."
          );
        }

        setFarms(data);

        if (data.length > 0 && data[0].ponds.length > 0) {
          const firstFarm = data[0];
          const firstPond = firstFarm.ponds[0];
          setFarmId(String(firstFarm.id));
          setPondId(String(firstPond.id));
          fetchForecast(String(firstFarm.id), String(firstPond.id));
        }
      } catch (err) {
        setError(
          err.message || "Could not load farms. Check that FastAPI is running."
        );
      } finally {
        setFarmsLoading(false);
      }
    }

    loadFarms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleFarmChange(event) {
    const newFarmId = event.target.value;
    const newFarm = farms.find((farm) => String(farm.id) === newFarmId);

    setFarmId(newFarmId);
    setPondId(newFarm?.ponds?.[0] ? String(newFarm.ponds[0].id) : "");
    setForecast(null);
    setError("");
  }

  function handlePondChange(event) {
    setPondId(event.target.value);
    setForecast(null);
    setError("");
  }

  const dailyData =
    forecast?.daily_forecast?.map((item) => ({
      ...item,
      dateLabel: new Date(`${item.date}T00:00:00`).toLocaleDateString(
        "en-IN",
        { day: "2-digit", month: "short" }
      ),
    })) || [];

  return (
    <div className="forecast-page">
      <div className="forecast-heading">
        <div>
          <h2>Weekly Feed Forecast</h2>
          <p>AI-powered feed quantity predictions using your farm records.</p>
        </div>
        <span className="forecast-tag">Random Forest ML</span>
      </div>

      <div className="forecast-controls">
        <div className="forecast-field">
          <label htmlFor="farmSelect">Farm</label>
          <select
            id="farmSelect"
            value={farmId}
            onChange={handleFarmChange}
            disabled={loading || farmsLoading}
          >
            {farmsLoading && <option value="">Loading farms...</option>}
            {farms.map((farm) => (
              <option key={farm.id} value={farm.id}>
                {farm.name}
              </option>
            ))}
          </select>
        </div>

        <div className="forecast-field">
          <label htmlFor="pondSelect">Pond</label>
          <select
            id="pondSelect"
            value={pondId}
            onChange={handlePondChange}
            disabled={loading || farmsLoading || pondsOfFarm.length === 0}
          >
            {pondsOfFarm.map((pond) => (
              <option key={pond.id} value={pond.id}>
                {pond.label} ({pond.code})
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={() => fetchForecast()}
          disabled={loading || farmsLoading || !pondId}
        >
          {loading ? "Generating..." : "Generate Forecast"}
        </button>
      </div>

      {loading && (
        <div className="forecast-message">
          Fetching records for {selectedFarm?.name} /{" "}
          {selectedPond?.label || "pond"} and generating predictions...
        </div>
      )}

      {error && (
        <div className="forecast-error" role="alert">
          <strong>Forecast unavailable</strong>
          <p>{error}</p>
        </div>
      )}

      {forecast && !loading && (
        <>
          <div className="forecast-kpis">
            <div className="forecast-card">
              <span>Farm / Pond</span>
              <strong>
                {forecast.farm_name} · Pond {forecast.pond_number}
              </strong>
              <small>{forecast.pond_code}</small>
            </div>

            <div className="forecast-card">
              <span>Total predicted feed</span>
              <strong>
                {Number(forecast.total_predicted_feed_kg).toFixed(2)} kg
              </strong>
            </div>

            <div className="forecast-card">
              <span>Daily average</span>
              <strong>
                {(
                  Number(forecast.total_predicted_feed_kg) /
                  forecast.forecast_days
                ).toFixed(2)}{" "}
                kg
              </strong>
            </div>

            <div className="forecast-card">
              <span>Forecast duration</span>
              <strong>{forecast.forecast_days} days</strong>
            </div>
          </div>

          <section className="forecast-panel">
            <h3>Daily Predicted Feed Quantity</h3>
            <p>Estimated feed quantity for each forecast day.</p>

            <div className="forecast-chart">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="dateLabel" />
                  <YAxis
                    label={{
                      value: "Feed (kg)",
                      angle: -90,
                      position: "insideLeft",
                    }}
                  />
                  <Tooltip
                    formatter={(value) => [
                      `${Number(value).toFixed(2)} kg`,
                      "Predicted feed",
                    ]}
                    labelFormatter={(_, payload) =>
                      payload?.[0]?.payload?.date || ""
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="predicted_feed_kg"
                    name="Predicted feed"
                    stroke="#16876a"
                    strokeWidth={3}
                    dot={{ r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="forecast-panel">
            <h3>Seven-Day Forecast Details</h3>

            <div className="forecast-table-wrap">
              <table className="forecast-table">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Date</th>
                    <th>DOC</th>
                    <th>Predicted Feed (kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyData.map((item) => (
                    <tr key={item.day}>
                      <td>{item.day}</td>
                      <td>{item.date}</td>
                      <td>{item.doc}</td>
                      <td>{Number(item.predicted_feed_kg).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th colSpan="3">Total</th>
                    <th>
                      {Number(forecast.total_predicted_feed_kg).toFixed(2)} kg
                    </th>
                  </tr>
                </tfoot>
              </table>
            </div>
          </section>

          <p className="forecast-note">
            Experimental forecast: growth and water-quality measurements are
            held constant, and each predicted feed value is reused as the
            next day's previous-feed input. Validate model accuracy before
            using these values as farm feeding instructions.
          </p>
        </>
      )}
    </div>
  );
}