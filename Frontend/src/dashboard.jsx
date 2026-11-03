
import { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import "./dashboard.css";

const API = "http://localhost:8000";

const AQUA = "#06b6d4";
const AQUA_DARK = "#0891b2";

const PALETTE = [
  "#2b7bba", "#7b5cc4", AQUA, "#e49a35",
  "#dc2626", "#0e7490", "#0ea5e9", "#d946ef",
];

/* ---------- Helpers ---------- */

async function fetchRecords(endpoint) {
  const response = await fetch(`${API}${endpoint}`);

  if (!response.ok) {
    throw new Error(`${endpoint} returned ${response.status}`);
  }

  const result = await response.json();

  if (Array.isArray(result)) return result;

  if (result && typeof result === "object") {
    for (const value of Object.values(result)) {
      if (Array.isArray(value)) return value;
    }
  }

  return [];
}

function getValue(record, ...keys) {
  for (const key of keys) {
    if (record?.[key] !== undefined && record?.[key] !== null) {
      return record[key];
    }
  }
  return null;
}

function num(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function nonNegative(value) {
  return value !== null && value !== undefined && value >= 0
    ? value
    : null;
}

function chartNum(record, ...keys) {
  return nonNegative(num(getValue(record, ...keys)));
}

function countNegative(records, ...keys) {
  return records.filter((record) => {
    const value = num(getValue(record, ...keys));
    return value !== null && value < 0;
  }).length;
}

function fmt(value, digits = 2) {
  return value === null || value === undefined || !Number.isFinite(value)
    ? "—"
    : value.toLocaleString("en-IN", {
        maximumFractionDigits: digits,
      });
}

function dateOf(record, ...keys) {
  const value = getValue(record, ...keys);
  return value ? String(value).slice(0, 10) : "";
}

function farmId(f) {
  return getValue(f, "farm_id", "id");
}

function pondId(p) {
  return getValue(p, "pond_id", "id");
}

function farmLabel(f) {
  const name = getValue(f, "farm_name", "name") || `Farm ${farmId(f)}`;
  const place = getValue(f, "location", "district", "village");

  return place ? `${name} — ${place}` : name;
}

function pondCode(p) {
  return (
    getValue(p, "pond_code", "pond_name", "name") ||
    `Pond ${pondId(p)}`
  );
}

function pondSpecies(p) {
  return getValue(
    p,
    "species",
    "culture_species",
    "culture_type",
    "culture"
  );
}

function pondLabel(p) {
  const species = pondSpecies(p);
  return species ? `${pondCode(p)} — ${species}` : pondCode(p);
}

const GROWTH_DATES = ["sampling_date", "measurement_date", "date"];
const WATER_DATES = ["measurement_date", "date", "recorded_at"];
const FEED_DATES = ["feed_date", "feeding_date", "date"];
const HARVEST_DATES = ["harvest_date", "date", "recorded_at"];

function filterByPeriod(records, dateKeys, period, anchorDate) {
  if (period === "all" || !anchorDate) return records;

  const days = period === "week" ? 7 : 30;

  const end = new Date(`${anchorDate}T23:59:59`);
  const start = new Date(end);

  start.setDate(start.getDate() - (days - 1));

  return records.filter((record) => {
    const date = dateOf(record, ...dateKeys);

    if (!date) return false;

    const value = new Date(`${date}T12:00:00`);

    return value >= start && value <= end;
  });
}

function sortOldestFirst(records, dateKeys) {
  return [...records].sort((a, b) => {
    const byDate = dateOf(a, ...dateKeys).localeCompare(
      dateOf(b, ...dateKeys)
    );

    if (byDate !== 0) return byDate;

    return (
      (num(getValue(a, "doc")) ?? 0) -
      (num(getValue(b, "doc")) ?? 0)
    );
  });
}

function sum(records, ...keys) {
  return records.reduce(
    (total, record) => total + (chartNum(record, ...keys) || 0),
    0
  );
}

const FEED_KEYS = ["feed_quantity_kg", "feed_kg", "quantity_kg"];
const ABW_KEYS = ["avg_weight_g", "abw", "average_weight_g"];
const BIOMASS_KEYS = ["biomass_kg", "biomass"];

const SURVIVAL_KEYS = [
  "estimated_survival_pct",
  "survival_pct",
  "survival",
];

const OXYGEN_KEYS = ["dissolved_oxygen", "do", "oxygen"];
const TEMPERATURE_KEYS = ["temperature_c", "temperature"];
const PH_KEYS = ["ph", "pH"];
const SALINITY_KEYS = ["salinity_ppt", "salinity"];
const AMMONIA_KEYS = ["ammonia_mg_l", "ammonia"];

const HARVEST_KEYS = [
  "harvest_quantity_kg",
  "harvest_kg",
  "quantity_kg",
  "total_harvest_kg",
  "biomass_kg",
];

const forPondId = (records, id) =>
  records.filter(
    (record) => String(getValue(record, "pond_id")) === String(id)
  );

/* ---------- ADG Tooltip ---------- */

function ADGTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const row = payload[0].payload;

  return (
    <div
      style={{
        background: "#ffffff",
        padding: "12px 15px",
        border: "1px solid #dbe4ea",
        borderRadius: "10px",
        boxShadow: "0 5px 18px rgba(0,0,0,0.1)",
      }}
    >
      <strong>DOC: {row.doc}</strong>

      <p>ADG: {fmt(row.adg, 3)} g/day</p>

      <p>Source: {row.adgSource}</p>
    </div>
  );
}

/* ---------- Chart Card ---------- */

function ChartCard({
  title,
  subtitle,
  count,
  hasData,
  emptyText,
  wide,
  height = 260,
  children,
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <article
        className={wide ? "db-card db-wide" : "db-card"}
        onClick={() => hasData && setExpanded(true)}
        onKeyDown={(event) => {
          if (hasData && (event.key === "Enter" || event.key === " ")) {
            event.preventDefault();
            setExpanded(true);
          }
        }}
        role={hasData ? "button" : undefined}
        tabIndex={hasData ? 0 : undefined}
        aria-label={hasData ? `Expand ${title} chart` : undefined}
        style={{ cursor: hasData ? "pointer" : "default" }}
      >
        <div className="db-card-head">
          <div>
            <h3>{title}</h3>
            <p>{subtitle}</p>
          </div>

          {count !== undefined && (
            <span className="db-pill">{count}</span>
          )}
        </div>

        {hasData ? (
          <>
            <ResponsiveContainer width="100%" height={height}>
              {children}
            </ResponsiveContainer>

            <div className="db-expand-hint">
              ↗ Click chart to expand
            </div>
          </>
        ) : (
          <p className="db-muted">
            {emptyText || "No data for this pond."}
          </p>
        )}
      </article>

      {expanded && (
        <div
          className="db-chart-modal"
          onClick={() => setExpanded(false)}
          role="presentation"
        >
          <section
            className="db-chart-modal-content"
            role="dialog"
            aria-modal="true"
            aria-label={`${title} expanded chart`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="db-chart-modal-header">
              <div>
                <h2>{title}</h2>
                <p>{subtitle}</p>
              </div>

              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="db-chart-close"
                aria-label="Close expanded chart"
              >
                ×
              </button>
            </div>

            <div className="db-chart-modal-plot">
              <ResponsiveContainer width="100%" height="100%">
                {children}
              </ResponsiveContainer>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

/* ---------- Dashboard Tabs ---------- */

const TABS = [
  { id: "growth", label: "Growth" },
  { id: "water", label: "Water Quality" },
  { id: "feed", label: "Feed" },
  { id: "compare", label: "Farm Comparison" },
];

/* ---------- Main Dashboard ---------- */

export default function Dashboard() {
  const [farms, setFarms] = useState([]);
  const [ponds, setPonds] = useState([]);
  const [water, setWater] = useState([]);
  const [growth, setGrowth] = useState([]);
  const [feed, setFeed] = useState([]);
  const [harvest, setHarvest] = useState([]);
  const [stocking, setStocking] = useState([]);

  const [selectedFarm, setSelectedFarm] = useState("");
  const [selectedPond, setSelectedPond] = useState("");

  const [tab, setTab] = useState("growth");
  const [period, setPeriod] = useState("all");

  const [loading, setLoading] = useState(true);
  const [problems, setProblems] = useState([]);

  /* ---------- Load database records ---------- */

  useEffect(() => {
    let active = true;

    async function load() {
      const endpoints = [
        "/api/farms/",
        "/api/ponds/",
        "/api/water-quality/",
        "/api/growth/",
        "/api/feed/",
        "/api/harvest/",
        "/api/stocking/",
      ];

      const results = await Promise.allSettled(
        endpoints.map(fetchRecords)
      );

      if (!active) return;

      const issues = [];

      const data = results.map((result, index) => {
        if (result.status === "fulfilled") {
          if (result.value.length === 0) {
            issues.push(`${endpoints[index]} returned no records.`);
          }

          return result.value;
        }

        issues.push(result.reason.message);
        return [];
      });

      setFarms(data[0]);
      setPonds(data[1]);
      setWater(data[2]);
      setGrowth(data[3]);
      setFeed(data[4]);
      setHarvest(data[5]);
      setStocking(data[6]);

      setProblems(issues);

      if (data[0].length > 0) {
        setSelectedFarm(String(farmId(data[0][0])));
      }

      setLoading(false);
    }

    load();

    return () => {
      active = false;
    };
  }, []);

  /* ---------- Farm and pond selection ---------- */

  const farmPonds = useMemo(
    () =>
      ponds.filter(
        (p) => String(getValue(p, "farm_id")) === String(selectedFarm)
      ),
    [ponds, selectedFarm]
  );

  useEffect(() => {
    const exists = farmPonds.some(
      (p) => String(pondId(p)) === String(selectedPond)
    );

    if (!exists) {
      setSelectedPond(
        farmPonds.length ? String(pondId(farmPonds[0])) : ""
      );
    }
  }, [farmPonds, selectedPond]);

  const farm = farms.find(
    (f) => String(farmId(f)) === String(selectedFarm)
  );

  const pond = farmPonds.find(
    (p) => String(pondId(p)) === String(selectedPond)
  );

  /* ---------- Date range ---------- */

  const periodAnchor = useMemo(() => {
    const dated = [
      ...forPondId(growth, selectedPond).map((r) =>
        dateOf(r, ...GROWTH_DATES)
      ),
      ...forPondId(water, selectedPond).map((r) =>
        dateOf(r, ...WATER_DATES)
      ),
      ...forPondId(feed, selectedPond).map((r) =>
        dateOf(r, ...FEED_DATES)
      ),
      ...forPondId(harvest, selectedPond).map((r) =>
        dateOf(r, ...HARVEST_DATES)
      ),
    ]
      .filter(Boolean)
      .sort();

    return dated[dated.length - 1] || "";
  }, [growth, water, feed, harvest, selectedPond]);

  const pondWater = useMemo(
    () =>
      sortOldestFirst(
        filterByPeriod(
          forPondId(water, selectedPond),
          WATER_DATES,
          period,
          periodAnchor
        ),
        WATER_DATES
      ),
    [water, selectedPond, period, periodAnchor]
  );

  const pondGrowth = useMemo(
    () =>
      sortOldestFirst(
        filterByPeriod(
          forPondId(growth, selectedPond),
          GROWTH_DATES,
          period,
          periodAnchor
        ),
        GROWTH_DATES
      ),
    [growth, selectedPond, period, periodAnchor]
  );

  const pondFeed = useMemo(
    () =>
      sortOldestFirst(
        filterByPeriod(
          forPondId(feed, selectedPond),
          FEED_DATES,
          period,
          periodAnchor
        ),
        FEED_DATES
      ),
    [feed, selectedPond, period, periodAnchor]
  );

  /* ---------- Growth calculations ---------- */

  const growthChart = useMemo(() => {
    const rows = [];

    pondGrowth.forEach((record, index) => {
      const doc = num(getValue(record, "doc")) ?? index + 1;

      const rowAbw = chartNum(record, ...ABW_KEYS);

      const previous = rows[rows.length - 1];

      let adg = num(
        getValue(record, "adg_g", "adg", "avg_daily_gain_g")
      );

      const databaseADG = adg;

      if (
        adg === null &&
        previous &&
        previous.abw !== null &&
        rowAbw !== null &&
        doc > previous.doc
      ) {
        adg = (rowAbw - previous.abw) / (doc - previous.doc);
      }

      const roundedADG =
        adg !== null ? Number(adg.toFixed(3)) : null;

      rows.push({
        doc,
        date: dateOf(record, ...GROWTH_DATES),
        samplingId: getValue(record, "sampling_id"),
        pondId: getValue(record, "pond_id"),

        abw: rowAbw,
        biomass: chartNum(record, ...BIOMASS_KEYS),
        survival: chartNum(record, ...SURVIVAL_KEYS),

        // Negative ADG stays hidden without generating a warning.
        adg:
          roundedADG !== null && roundedADG < 0
            ? null
            : roundedADG,

        adgSource:
          databaseADG !== null
            ? "Database"
            : roundedADG !== null
              ? "Calculated"
              : "Unavailable",
      });
    });

    return rows;
  }, [pondGrowth]);

  /* ---------- Other negative values ---------- */

  const hiddenNegatives = useMemo(
    () =>
      [
        ["ABW", countNegative(pondGrowth, ...ABW_KEYS)],
        ["Biomass", countNegative(pondGrowth, ...BIOMASS_KEYS)],
        ["Survival", countNegative(pondGrowth, ...SURVIVAL_KEYS)],
        ["Oxygen", countNegative(pondWater, ...OXYGEN_KEYS)],
        ["Temperature", countNegative(pondWater, ...TEMPERATURE_KEYS)],
        ["pH", countNegative(pondWater, ...PH_KEYS)],
        ["Salinity", countNegative(pondWater, ...SALINITY_KEYS)],
        ["Ammonia", countNegative(pondWater, ...AMMONIA_KEYS)],
        ["Feed", countNegative(pondFeed, ...FEED_KEYS)],
      ].filter(([, count]) => count > 0),
    [pondGrowth, pondWater, pondFeed]
  );

  /* ---------- Daily feed series ---------- */

  const dailyFeed = useMemo(
    () =>
      Object.values(
        pondFeed.reduce((groups, record) => {
          const date = dateOf(record, ...FEED_DATES);
          const quantity = chartNum(record, ...FEED_KEYS);

          if (!date || quantity === null) return groups;

          if (!groups[date]) {
            groups[date] = { date, feed: 0 };
          }

          groups[date].feed += quantity;

          return groups;
        }, {})
      ),
    [pondFeed]
  );

  const feedVsGrowth = useMemo(() => {
    return growthChart
      .filter((row) => row.date)
      .map((row) => {
        const cumulativeFeed = dailyFeed
          .filter((d) => d.date <= row.date)
          .reduce((total, d) => total + d.feed, 0);

        const fcr =
          row.biomass && row.biomass > 0
            ? Number((cumulativeFeed / row.biomass).toFixed(2))
            : null;

        return {
          doc: row.doc,
          cumulativeFeed: Number(cumulativeFeed.toFixed(1)),
          biomass: row.biomass,
          fcr,
        };
      });
  }, [growthChart, dailyFeed]);

  /* ---------- Water quality series ---------- */

  const waterChart = useMemo(
    () =>
      pondWater.map((record) => ({
        date: dateOf(record, ...WATER_DATES),
        oxygen: chartNum(record, ...OXYGEN_KEYS),
        temperature: chartNum(record, ...TEMPERATURE_KEYS),
        ph: chartNum(record, ...PH_KEYS),
        salinity: chartNum(record, ...SALINITY_KEYS),
        ammonia: chartNum(record, ...AMMONIA_KEYS),
      })),
    [pondWater]
  );

  const hasWater = (key) =>
    waterChart.some((row) => row[key] !== null);

  const oxygenVsTemp = waterChart.filter(
    (row) => row.oxygen !== null && row.temperature !== null
  );

  /* ---------- Farm comparison calculations ---------- */

  const pondSummary = useMemo(
    () =>
      farmPonds.map((p) => {
        const id = pondId(p);

        const samples = sortOldestFirst(
          filterByPeriod(
            forPondId(growth, id),
            GROWTH_DATES,
            period,
            periodAnchor
          ),
          GROWTH_DATES
        );

        const last = samples[samples.length - 1];

        return {
          pond: pondCode(p),
          abw: chartNum(last, ...ABW_KEYS),
          biomass: chartNum(last, ...BIOMASS_KEYS),

          feed: Number(
            sum(
              filterByPeriod(
                forPondId(feed, id),
                FEED_DATES,
                period,
                periodAnchor
              ),
              ...FEED_KEYS
            ).toFixed(1)
          ),

          harvest: Number(
            sum(
              filterByPeriod(
                forPondId(harvest, id),
                HARVEST_DATES,
                period,
                periodAnchor
              ),
              ...HARVEST_KEYS
            ).toFixed(1)
          ),
        };
      }),
    [farmPonds, growth, feed, harvest, period, periodAnchor]
  );

  const overlay = useMemo(() => {
    const docs = new Set();

    const perPond = farmPonds.map((p) => {
      const samples = sortOldestFirst(
        filterByPeriod(
          forPondId(growth, pondId(p)),
          GROWTH_DATES,
          period,
          periodAnchor
        ),
        GROWTH_DATES
      );

      const byDoc = {};

      samples.forEach((record, index) => {
        const doc = num(getValue(record, "doc")) ?? index + 1;
        const value = chartNum(record, ...ABW_KEYS);

        if (value !== null) {
          byDoc[doc] = value;
          docs.add(doc);
        }
      });

      return {
        code: pondCode(p),
        byDoc,
      };
    });

    const rows = [...docs]
      .sort((a, b) => a - b)
      .map((doc) => {
        const row = { doc };

        perPond.forEach((p) => {
          if (p.byDoc[doc] !== undefined) {
            row[p.code] = p.byDoc[doc];
          }
        });

        return row;
      });

    return {
      rows,
      codes: perPond.map((p) => p.code),
    };
  }, [farmPonds, growth, period, periodAnchor]);

  if (loading) {
    return <div className="db-page">Loading dashboard…</div>;
  }

  const area = num(
    getValue(pond, "area_acres", "area", "pond_area_acres")
  );

  /* ---------- Dashboard UI ---------- */

  return (
    <div className="db-page">
      <header className="db-topbar">
        <div className="db-brand-mark">A</div>

        <div className="db-brand-copy">
          <span>AQUALLM · INTELLIGENCE</span>
          <h1>Aquaculture Analytics</h1>
          <p>
            Monitor pond performance, water quality and feed trends.
          </p>
        </div>

        <div className="db-live-tag">
          <i />
          DATABASE CONNECTED
        </div>
      </header>

      {problems.length > 0 && (
        <div className="db-alert">
          <strong>Some data did not load</strong>

          <ul>
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>

          <small>
            Open each endpoint in your browser (for example {API}
            /api/farms/) to check what the backend returns.
          </small>
        </div>
      )}

      {/* Farm and pond selection */}

      <section className="db-card">
        <div className="db-card-head">
          <h2>Farm &amp; Pond Selection</h2>
          <span>Choose a farm and pond</span>
        </div>

        <div className="db-selects">
          <label>
            <span>Farm</span>

            <select
              value={selectedFarm}
              onChange={(event) => setSelectedFarm(event.target.value)}
            >
              {farms.length === 0 && (
                <option value="">No farms found</option>
              )}

              {farms.map((f) => (
                <option key={farmId(f)} value={farmId(f)}>
                  {farmLabel(f)}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Pond</span>

            <select
              value={selectedPond}
              onChange={(event) => setSelectedPond(event.target.value)}
              disabled={farmPonds.length === 0}
            >
              {farmPonds.length === 0 && (
                <option value="">No ponds for this farm</option>
              )}

              {farmPonds.map((p) => (
                <option key={pondId(p)} value={pondId(p)}>
                  {pondLabel(p)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {/* Database record counts */}

      <div className="db-chips">
        <span>Farms: <b>{farms.length}</b></span>
        <span>Ponds: <b>{ponds.length}</b></span>
        <span>Stocking: <b>{stocking.length}</b></span>
        <span>Feed: <b>{feed.length}</b></span>
        <span>Water: <b>{water.length}</b></span>
        <span>Growth: <b>{growth.length}</b></span>
        <span>Harvest: <b>{harvest.length}</b></span>
      </div>

      {!pond ? (
        <section className="db-card db-empty">
          <h3>No pond selected</h3>
          <p>Choose a farm that has ponds to see its data.</p>
        </section>
      ) : (
        <>
          {/* Selected pond banner */}

          <section className="db-banner">
            <div>
              <small>SELECTED POND</small>
              <h2>{pondCode(pond)}</h2>
              <p>
                {farm ? farmLabel(farm).replace(" — ", " • ") : ""}
              </p>
            </div>

            <div className="db-banner-meta">
              <div>
                <small>CULTURE</small>
                <b>{pondSpecies(pond) || "—"}</b>
              </div>

              <div>
                <small>AREA</small>
                <b>{area !== null ? `${fmt(area)} acres` : "—"}</b>
              </div>

              <div>
                <small>STATUS</small>
                <b>{getValue(pond, "status", "pond_status") || "—"}</b>
              </div>
            </div>
          </section>

          {/* Visualization period */}

          <section className="db-period-bar">
            <div className="db-period-copy">
              <span className="db-eyebrow">VISUALIZATION RANGE</span>
              <strong>Choose the data period</strong>

              <small>
                {period === "all"
                  ? "Showing every available record in the database for this pond"
                  : `Showing records up to ${
                      periodAnchor || "the latest available date"
                    }`}
              </small>
            </div>

            <div
              className="db-period-options"
              role="group"
              aria-label="Choose visualization period"
            >
              <button
                type="button"
                className={period === "week" ? "selected" : ""}
                onClick={() => setPeriod("week")}
              >
                Last Week
                <span>7 days</span>
              </button>

              <button
                type="button"
                className={period === "month" ? "selected" : ""}
                onClick={() => setPeriod("month")}
              >
                Last Month
                <span>30 days</span>
              </button>

              <button
                type="button"
                className={period === "all" ? "selected" : ""}
                onClick={() => setPeriod("all")}
              >
                Whole Database
                <span>All records</span>
              </button>
            </div>
          </section>

          {/* Tabs */}

          <div className="db-tabs">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={tab === t.id ? "db-tab active" : "db-tab"}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* General negative-value warning */}

          {tab !== "compare" && hiddenNegatives.length > 0 && (
            <div className="db-alert">
              <strong>Negative values are hidden from the charts</strong>

              <p>
                {hiddenNegatives
                  .map(([name, count]) => `${name}: ${count}`)
                  .join(" | ")}
                . Please verify these records in the database.
              </p>
            </div>
          )}

          {/* GROWTH */}

          {tab === "growth" && (
            <>
              <section className="db-charts">

                <ChartCard
                  title="Average Body Weight vs DOC"
                  subtitle="Shrimp weight progression during culture"
                  count={growthChart.length}
                  hasData={growthChart.some((r) => r.abw !== null)}
                >
                  <LineChart data={growthChart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="doc" />
                    <YAxis />
                    <Tooltip />

                    <Line
                      type="monotone"
                      dataKey="abw"
                      name="ABW (g)"
                      stroke="#2b7bba"
                      strokeWidth={3}
                      dot
                      connectNulls
                    />
                  </LineChart>
                </ChartCard>

                <ChartCard
                  title="Biomass vs DOC"
                  subtitle="Estimated biomass progression"
                  count={growthChart.length}
                  hasData={growthChart.some((r) => r.biomass !== null)}
                >
                  <LineChart data={growthChart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="doc" />
                    <YAxis />
                    <Tooltip />

                    <Line
                      type="monotone"
                      dataKey="biomass"
                      name="Biomass (kg)"
                      stroke="#7b5cc4"
                      strokeWidth={3}
                      dot
                      connectNulls
                    />
                  </LineChart>
                </ChartCard>

                <ChartCard
                  title="Average Daily Growth (ADG)"
                  subtitle="Growth per day between samples"
                  count={growthChart.filter((r) => r.adg !== null).length}
                  hasData={growthChart.some((r) => r.adg !== null)}
                  emptyText="Not enough valid growth samples to show ADG."
                >
                  <BarChart data={growthChart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="doc" />
                    <YAxis domain={[0, "auto"]} />
                    <Tooltip content={<ADGTooltip />} />

                    <Bar
                      dataKey="adg"
                      name="ADG (g/day)"
                      fill="#e49a35"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ChartCard>

                <ChartCard
                  title="Survival vs DOC"
                  subtitle="Estimated survival rate (%)"
                  count={growthChart.filter((r) => r.survival !== null).length}
                  hasData={growthChart.some((r) => r.survival !== null)}
                  emptyText="No survival data found in the growth records."
                >
                  <LineChart data={growthChart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="doc" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />

                    <Line
                      type="monotone"
                      dataKey="survival"
                      name="Survival (%)"
                      stroke={AQUA_DARK}
                      strokeWidth={3}
                      dot
                      connectNulls
                    />
                  </LineChart>
                </ChartCard>

              </section>
            </>
          )}

          {/* WATER QUALITY */}

          {tab === "water" && (
            <section className="db-charts">

              <ChartCard
                title="Dissolved Oxygen & Temperature"
                subtitle="Red line marks the 5 mg/L oxygen watch level"
                count={waterChart.length}
                hasData={hasWater("oxygen") || hasWater("temperature")}
              >
                <LineChart data={waterChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                  <YAxis yAxisId="left" domain={[0, "auto"]} />
                  <YAxis yAxisId="right" orientation="right" domain={[0, "auto"]} />
                  <Tooltip />
                  <Legend />

                  <ReferenceLine
                    yAxisId="left"
                    y={5}
                    stroke="#dc2626"
                    strokeDasharray="4 4"
                  />

                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="oxygen"
                    name="Oxygen (mg/L)"
                    stroke={AQUA_DARK}
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />

                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="temperature"
                    name="Temperature (°C)"
                    stroke="#e49a35"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ChartCard>

              <ChartCard
                title="Oxygen vs Temperature"
                subtitle="Each dot is one reading"
                count={oxygenVsTemp.length}
                hasData={oxygenVsTemp.length > 0}
                emptyText="Needs readings with both oxygen and temperature."
              >
                <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" />

                  <XAxis
                    type="number"
                    dataKey="temperature"
                    name="Temperature"
                    unit="°C"
                    domain={["auto", "auto"]}
                  />

                  <YAxis
                    type="number"
                    dataKey="oxygen"
                    name="Oxygen"
                    unit=" mg/L"
                    domain={[0, "auto"]}
                  />

                  <Tooltip cursor={{ strokeDasharray: "3 3" }} />

                  <Scatter
                    data={oxygenVsTemp}
                    fill={AQUA_DARK}
                    fillOpacity={0.6}
                  />
                </ScatterChart>
              </ChartCard>

              <ChartCard
                title="pH"
                subtitle="Aqua band shows the 7.5 – 8.5 range"
                count={waterChart.filter((r) => r.ph !== null).length}
                hasData={hasWater("ph")}
              >
                <LineChart data={waterChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />

                  <YAxis
                    domain={[
                      (min) => Math.max(0, Math.min(min, 7.4) - 0.2),
                      (max) => Math.max(max, 8.6) + 0.2,
                    ]}
                    tickFormatter={(value) => Number(value).toFixed(1)}
                  />

                  <Tooltip />

                  <ReferenceArea
                    y1={7.5}
                    y2={8.5}
                    fill={AQUA}
                    fillOpacity={0.12}
                  />

                  <Line
                    type="monotone"
                    dataKey="ph"
                    name="pH"
                    stroke="#7b5cc4"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ChartCard>

              <ChartCard
                title="Salinity"
                subtitle="Salinity in ppt"
                count={waterChart.filter((r) => r.salinity !== null).length}
                hasData={hasWater("salinity")}
              >
                <LineChart data={waterChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />

                  <Line
                    type="monotone"
                    dataKey="salinity"
                    name="Salinity (ppt)"
                    stroke="#2b7bba"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ChartCard>

              <ChartCard
                title="Ammonia"
                subtitle="Red line marks the 0.1 mg/L watch level"
                count={waterChart.filter((r) => r.ammonia !== null).length}
                hasData={hasWater("ammonia")}
              >
                <LineChart data={waterChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                  <YAxis domain={[0, (max) => Math.max(max, 0.12)]} />
                  <Tooltip />

                  <ReferenceLine
                    y={0.1}
                    stroke="#dc2626"
                    strokeDasharray="4 4"
                  />

                  <Line
                    type="monotone"
                    dataKey="ammonia"
                    name="Ammonia (mg/L)"
                    stroke="#dc2626"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ChartCard>

            </section>
          )}

          {/* FEED */}

          {tab === "feed" && (
            <section className="db-charts">

              <ChartCard
                title="Daily Feed"
                subtitle={
                  period === "all"
                    ? "Daily feed across all available records"
                    : period === "week"
                      ? "Daily feed during the last 7 recorded days"
                      : "Daily feed during the last 30 recorded days"
                }
                count={dailyFeed.length}
                hasData={dailyFeed.length > 0}
                emptyText="No feed records for this pond."
              >
                <BarChart data={dailyFeed}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={20} />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />

                  <Bar
                    dataKey="feed"
                    name="Feed (kg)"
                    fill={AQUA}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartCard>

              <ChartCard
                title="Cumulative Feed vs Biomass"
                subtitle="At each growth sampling (by DOC)"
                count={feedVsGrowth.length}
                hasData={feedVsGrowth.length > 0}
                emptyText="Needs growth samples with dates and feed records."
              >
                <LineChart data={feedVsGrowth}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="doc" />
                  <YAxis yAxisId="left" domain={[0, "auto"]} />
                  <YAxis yAxisId="right" orientation="right" domain={[0, "auto"]} />
                  <Tooltip />
                  <Legend />

                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="cumulativeFeed"
                    name="Cumulative feed (kg)"
                    stroke={AQUA}
                    strokeWidth={2}
                    dot
                    connectNulls
                  />

                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="biomass"
                    name="Biomass (kg)"
                    stroke="#7b5cc4"
                    strokeWidth={2}
                    dot
                    connectNulls
                  />
                </LineChart>
              </ChartCard>

              <ChartCard
                title="Approximate FCR"
                subtitle="Cumulative feed ÷ current biomass"
                count={feedVsGrowth.filter((r) => r.fcr !== null).length}
                hasData={feedVsGrowth.some((r) => r.fcr !== null)}
                emptyText="Needs growth biomass and feed records."
              >
                <LineChart data={feedVsGrowth}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="doc" />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />

                  <Line
                    type="monotone"
                    dataKey="fcr"
                    name="FCR"
                    stroke="#e49a35"
                    strokeWidth={3}
                    dot
                    connectNulls
                  />
                </LineChart>
              </ChartCard>

            </section>
          )}

          {/* FARM COMPARISON */}

          {tab === "compare" && (
            <section className="db-charts">

              <ChartCard
                title="Growth Curves of All Ponds"
                subtitle="ABW against DOC for every pond in this farm"
                count={overlay.codes.length}
                hasData={overlay.rows.length > 0}
                wide
                height={320}
              >
                <LineChart data={overlay.rows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="doc" />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />
                  <Legend />

                  {overlay.codes.map((code, index) => (
                    <Line
                      key={code}
                      type="monotone"
                      dataKey={code}
                      stroke={PALETTE[index % PALETTE.length]}
                      strokeWidth={code === pondCode(pond) ? 4 : 2}
                      dot={false}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ChartCard>

              <ChartCard
                title="Latest ABW by Pond"
                subtitle="All ponds in the selected farm"
                count={pondSummary.length}
                hasData={pondSummary.some((r) => r.abw !== null)}
              >
                <BarChart data={pondSummary}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="pond" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />

                  <Bar
                    dataKey="abw"
                    name="ABW (g)"
                    fill="#2b7bba"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartCard>

              <ChartCard
                title="Latest Biomass by Pond"
                subtitle="Estimated biomass (kg)"
                count={pondSummary.length}
                hasData={pondSummary.some((r) => r.biomass !== null)}
              >
                <BarChart data={pondSummary}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="pond" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />

                  <Bar
                    dataKey="biomass"
                    name="Biomass (kg)"
                    fill="#7b5cc4"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartCard>

              <ChartCard
                title="Total Feed by Pond"
                subtitle="All recorded feed (kg)"
                count={pondSummary.length}
                hasData={pondSummary.some((r) => r.feed > 0)}
              >
                <BarChart data={pondSummary}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="pond" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />

                  <Bar
                    dataKey="feed"
                    name="Feed (kg)"
                    fill={AQUA}
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartCard>

              <ChartCard
                title="Harvest by Pond"
                subtitle="Recorded harvest (kg)"
                count={pondSummary.length}
                hasData={pondSummary.some((r) => r.harvest > 0)}
              >
                <BarChart data={pondSummary}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="pond" tick={{ fontSize: 11 }} />
                  <YAxis domain={[0, "auto"]} />
                  <Tooltip />

                  <Bar
                    dataKey="harvest"
                    name="Harvest (kg)"
                    fill="#e49a35"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ChartCard>

            </section>
          )}
        </>
      )}
    </div>
  );
}
