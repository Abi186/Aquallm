import { useRef, useState } from "react";
import axios from "axios";
import "./Data Upload.css";

const API = "http://127.0.0.1:8000";

// value = what goes in /api/upload/{table_name}
const TABLES = [
  { value: "farms", label: "Farms" },
  { value: "ponds", label: "Ponds" },
  { value: "stocking_records", label: "Stocking" },
  { value: "feed_records", label: "Feed" },
  { value: "water_quality", label: "Water" },
  { value: "growth_sampling", label: "Growth" },
  { value: "harvest_records", label: "Harvest" },
];

const ALLOWED = [".csv", ".xlsx", ".xls"];

function formatError(err) {
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (detail) return JSON.stringify(detail, null, 2);
  return "Upload failed. Check that the backend is running.";
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function DataUpload() {
  const [tableName, setTableName] = useState(TABLES[0].value);
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  const tableLabel = TABLES.find((t) => t.value === tableName)?.label;

  let status = "No file";
  if (uploading) status = "Uploading";
  else if (result) status = "Uploaded";
  else if (error) status = "Failed";
  else if (file) status = "Ready";

  function chooseFile(selected) {
    setResult(null);
    setError("");

    if (!selected) {
      setFile(null);
      return;
    }

    const name = selected.name.toLowerCase();
    if (!ALLOWED.some((ext) => name.endsWith(ext))) {
      setFile(null);
      setError("Only .csv, .xlsx or .xls files are allowed.");
      return;
    }

    setFile(selected);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files?.[0]);
  }

  function clearFile() {
    setFile(null);
    setResult(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleUpload() {
    if (!file) {
      setError("Please choose a file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file); // field name must be "file"

    setUploading(true);
    setError("");
    setResult(null);

    try {
      const response = await axios.post(
        `${API}/api/upload/${tableName}`,
        formData
      );
      setResult(response.data);
    } catch (err) {
      setError(formatError(err));
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="upload-shell">
      <div className="upload-topbar">
        <h1>Upload Data</h1>
      </div>

      <div className="upload-body">
        {/* Selection card */}
        <section className="upload-card">
          <div className="upload-card-head">
            <h3>Table &amp; File Selection</h3>
            <span className="upload-hint">Choose a table and a file</span>
          </div>

          <div className="upload-field">
            <label htmlFor="uploadTable">Table</label>
            <select
              id="uploadTable"
              value={tableName}
              onChange={(event) => {
                setTableName(event.target.value);
                setResult(null);
                setError("");
              }}
              disabled={uploading}
            >
              {TABLES.map((table) => (
                <option key={table.value} value={table.value}>
                  {table.label} ({table.value})
                </option>
              ))}
            </select>
          </div>

          <div
            className={`upload-dropzone ${dragging ? "dragging" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                inputRef.current?.click();
              }
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept={ALLOWED.join(",")}
              onChange={(event) => chooseFile(event.target.files?.[0])}
              hidden
            />
            <strong>Drag and drop a file here</strong>
            <span>or click to browse (.csv, .xlsx, .xls)</span>
          </div>
        </section>

        {/* Dark summary card (same style as Selected Pond) */}
        <section className="upload-hero">
          <div className="upload-hero-main">
            <span className="upload-hero-label">SELECTED FILE</span>
            <h2>{file ? file.name : "No file selected"}</h2>
            <p>Target table: {tableLabel}</p>
          </div>

          <div className="upload-hero-stats">
            <div>
              <span>TABLE</span>
              <strong>{tableLabel}</strong>
            </div>
            <div>
              <span>TYPE</span>
              <strong>
                {file ? file.name.split(".").pop().toUpperCase() : "-"}
              </strong>
            </div>
            <div>
              <span>SIZE</span>
              <strong>{file ? formatSize(file.size) : "-"}</strong>
            </div>
            <div>
              <span>STATUS</span>
              <strong
                className={`upload-status ${status
                  .toLowerCase()
                  .replace(" ", "-")}`}
              >
                {status}
              </strong>
            </div>
          </div>
        </section>

        <div className="upload-actions">
          <button
            type="button"
            className="upload-submit"
            onClick={handleUpload}
            disabled={uploading || !file}
          >
            {uploading ? "Uploading..." : `Upload to ${tableLabel}`}
          </button>
          <button
            type="button"
            className="upload-secondary"
            onClick={clearFile}
            disabled={uploading || !file}
          >
            Clear
          </button>
        </div>

        {error && (
          <div className="upload-alert upload-alert-error" role="alert">
            <strong>Upload failed</strong>
            <pre>{error}</pre>
          </div>
        )}

        {result && (
          <div className="upload-alert upload-alert-success" role="status">
            <strong>Upload completed</strong>
            {typeof result === "string" ? (
              <p>{result}</p>
            ) : (
              <>
                {result.message && <p>{result.message}</p>}
                <pre>{JSON.stringify(result, null, 2)}</pre>
              </>
            )}
          </div>
        )}

        <p className="upload-note">
          Column names in the file must match the table columns (for example
          pond_id, feed_date, feed_quantity_kg for Feed).
        </p>
      </div>
    </div>
  );
}