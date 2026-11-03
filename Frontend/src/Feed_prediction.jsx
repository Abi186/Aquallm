import { useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";

const API = "http://127.0.0.1:8000";

function formatError(err) {
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail) return JSON.stringify(detail);
  return "Prediction failed. Check that the backend is running.";
}

export default function FeedPrediction() {
  const [farms, setFarms] = useState([]);
  const [farmId, setFarmId] = useState("");
  const [pondId, setPondId] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef(0);

  const selectedFarm = farms.find((farm) => String(farm.id) === farmId);
  const pondsOfFarm = selectedFarm?.ponds || [];

  useEffect(() => {
    async function loadFarms() {
      try {
        const response = await axios.get(`${API}/api/feed-prediction/farms`);
        const data = response.data;
        setFarms(data);
        if (data.length > 0 && data[0].ponds.length > 0) {
          setFarmId(String(data[0].id));
          setPondId(String(data[0].ponds[0].id));
        }
      } catch (err) {
        setError(formatError(err));
      }
    }
    loadFarms();
  }, []);

  function resetResult() {
    requestRef.current += 1; // ignore any in-flight response
    setLoading(false);
    setResult(null);
    setError("");
  }

  function handleFarmChange(event) {
    const newFarmId = event.target.value;
    const newFarm = farms.find((farm) => String(farm.id) === newFarmId);
    setFarmId(newFarmId);
    setPondId(newFarm?.ponds?.[0] ? String(newFarm.ponds[0].id) : "");
    resetResult();
  }

  async function getPrediction() {
    if (!farmId || !pondId) {
      setError("Please select a farm and a pond.");
      return;
    }

    const requestId = ++requestRef.current;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await axios.get(
        `${API}/api/feed-prediction/${Number(farmId)}/${Number(pondId)}`
      );
      if (requestId !== requestRef.current) return;
      setResult(response.data);
    } catch (err) {
      if (requestId !== requestRef.current) return;
      setError(formatError(err));
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  }

  const chartData = result
    ? [
        {
          name: "Daily feed",
          historical: Number(result.historical_feed_kg ?? 0),
          predicted: Number(result.predicted_feed_kg ?? 0),
        },
      ]
    : [];

  return (
    <section className="feed-prediction">
      <h2>Shrimp Feed Prediction</h2>
      <p>
        Estimate daily feed quantity using the selected pond's available
        historical records.
      </p>

      <label htmlFor="feed-farm">Select farm</label>
      <select
        id="feed-farm"
        value={farmId}
        onChange={handleFarmChange}
        disabled={farms.length === 0}
      >
        {farms.map((farm) => (
          <option key={farm.id} value={farm.id}>
            {farm.name}
          </option>
        ))}
      </select>

      <label htmlFor="feed-pond">Select pond</label>
      <select
        id="feed-pond"
        value={pondId}
        onChange={(event) => {
          setPondId(event.target.value);
          resetResult();
        }}
        disabled={pondsOfFarm.length === 0}
      >
        {pondsOfFarm.map((pond) => (
          <option key={pond.id} value={pond.id}>
            {pond.label} ({pond.code})
          </option>
        ))}
      </select>

      <button onClick={getPrediction} disabled={loading || !pondId}>
        {loading ? "Predicting..." : "Predict feed quantity"}
      </button>

      {error && <p role="alert">{error}</p>}

      {result && (
        <>
          <div className="feed-prediction-result">
            <h3>Predicted daily feed</h3>
            <strong>{Number(result.predicted_feed_kg).toFixed(2)} kg</strong>
            <p>
              {result.farm_name} · Pond {result.pond_number} (
              {result.pond_code})
            </p>
            <p>{result.note}</p>
          </div>

          <h3>Historical vs predicted feed</h3>
          <div style={{ width: "100%", height: 300 }}>
            <ResponsiveContainer>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis
                  label={{
                    value: "Feed (kg)",
                    angle: -90,
                    position: "insideLeft",
                  }}
                />
                <Tooltip />
                <Legend />
                <Bar dataKey="historical" name="Historical feed (kg)" />
                <Bar dataKey="predicted" name="Predicted feed (kg)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  );
}