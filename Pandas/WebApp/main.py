"""
FastAPI single-page web app that replaces the earlier Streamlit UI.

Features:
- Top filters based on d1 columns (machine_id, part_number, tool_number), no auto-selection.
- Left: filtered d2 table. Right: average vs time chart.
- Uses vanilla HTML/CSS/JS with Chart.js (CDN) for a single-screen layout.
"""

from pathlib import Path
from typing import List, Optional

import pandas as pd
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import json
import logging
import os


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


DATA_CONFIG_PATH = Path(r"E:\Learning\TEAI Cup\Data\Parquet Data\latest_data.json")
FILTER_COLUMNS = ["machine_id", "part_number", "tool_number"]
TABLE_ROW_LIMIT = 400  # keep responses lightweight


app = FastAPI(title="Machine Stamping Web App", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_data():
    """Load all three datasets defined in latest_data.json."""
    logger.info("Loading datasets from config...")
    try:
        with DATA_CONFIG_PATH.open("r") as f:
            latest_data = json.load(f)
    except FileNotFoundError:
        logger.error("Config file not found at %s", DATA_CONFIG_PATH)
        raise
    except json.JSONDecodeError as exc:
        logger.error("Config file is not valid JSON: %s", exc)
        raise

    try:
        d1 = pd.read_parquet(latest_data["d1"])
        d2 = pd.read_parquet(latest_data["d2"])
        d3 = pd.read_parquet(latest_data["d3"])
    except Exception as exc:
        logger.error("Failed to read parquet files: %s", exc)
        raise

    # Normalize timestamp columns for d2
    if "timestamp" in d2.columns:
        d2["timestamp"] = pd.to_datetime(d2["timestamp"])

    logger.info(
        "Loaded datasets: d1=%s d2=%s d3=%s",
        d1.shape,
        d2.shape,
        d3.shape,
    )

    return d1, d2, d3


# Cache data in memory after first load
D1, D2, D3 = load_data()


def filter_d1(d1: pd.DataFrame, machine_ids, part_numbers, tool_numbers):
    df = d1.copy()
    if machine_ids:
        df = df[df["machine_id"].isin(machine_ids)]
    if part_numbers:
        df = df[df["part_number"].isin(part_numbers)]
    if tool_numbers:
        df = df[df["tool_number"].isin(tool_numbers)]
    return df


def filter_d2_by_d1(d2: pd.DataFrame, d1_filtered: pd.DataFrame):
    if d1_filtered.empty:
        return pd.DataFrame(columns=d2.columns)
    machines = d1_filtered["machine_id"].unique().tolist()
    return d2[d2["machine_id"].isin(machines)].copy()


def build_avg_time_series(df: pd.DataFrame):
    if df.empty or "timestamp" not in df.columns:
        return []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    if "value" in numeric_cols:
        target_col = "value"
    elif numeric_cols:
        target_col = numeric_cols[0]
    else:
        return []
    grouped = df.groupby("timestamp")[target_col].mean().reset_index()
    grouped.sort_values("timestamp", inplace=True)
    return [
        {
            "timestamp": ts.isoformat(),
            "avg": float(val),
        }
        for ts, val in zip(grouped["timestamp"], grouped[target_col])
    ]


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve a single-page app with inline HTML/CSS/JS."""
    return HTMLResponse(
        content=f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Machine Stamping Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg: #0f172a;
            --card: #111827;
            --accent: #38bdf8;
            --text: #e5e7eb;
            --muted: #9ca3af;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 16px;
            background: radial-gradient(circle at 20% 20%, #1e293b, #0f172a 45%), #0f172a;
            color: var(--text);
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            overflow: hidden;
        }}
        h1 {{ margin: 0 0 12px 0; font-size: 24px; letter-spacing: 0.5px; }}
        .card {{ background: var(--card); border: 1px solid #1f2937; border-radius: 12px; padding: 12px 14px; }}
        .filters {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 12px; }}
        label {{ display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }}
        select {{ width: 100%; padding: 8px; border-radius: 8px; border: 1px solid #1f2937; background: #0b1220; color: var(--text); }}
        button {{
            background: linear-gradient(90deg, #38bdf8, #22d3ee);
            color: #0b1220;
            border: none;
            padding: 10px 14px;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 600;
            letter-spacing: 0.3px;
            box-shadow: 0 8px 20px rgba(34, 211, 238, 0.25);
        }}
        button:disabled {{ opacity: 0.6; cursor: not-allowed; }}
        .layout {{ display: grid; grid-template-columns: 1fr 1.1fr; gap: 12px; height: calc(100vh - 150px); }}
        .table-wrap {{ overflow: auto; height: 100%; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th, td {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid #1f2937; }}
        th {{ position: sticky; top: 0; background: #0b1220; z-index: 2; }}
        .muted {{ color: var(--muted); font-size: 13px; margin-top: 8px; }}
        canvas {{ background: #0b1220; border-radius: 10px; padding: 8px; }}
        @media (max-width: 960px) {{ .layout {{ grid-template-columns: 1fr; height: auto; }} body {{ overflow: auto; }} }}
    </style>
</head>
<body>
    <h1>Machine Stamping Dashboard</h1>
    <div class="card">
        <div class="filters" id="filters"></div>
        <div style="display:flex;gap:8px;align-items:center;margin-top:6px;">
            <button id="applyBtn">Apply Filters</button>
            <span class="muted">No filters are pre-selected. Choose options, then click Apply.</span>
        </div>
    </div>

    <div class="layout">
        <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div><strong>Filtered Data (d2)</strong></div>
                <div class="muted" id="rowInfo"></div>
            </div>
            <div class="table-wrap">
                <table id="dataTable"></table>
            </div>
        </div>

        <div class="card">
            <div style="margin-bottom:6px;"><strong>Average vs Time</strong></div>
            <canvas id="chart" height="140"></canvas>
            <div class="muted" id="chartInfo"></div>
        </div>
    </div>

    <script>
        const filterOrder = ["machine_id", "part_number", "tool_number"];
        let chart;

        async function loadFilters() {{
            const res = await fetch('/api/filters');
            const data = await res.json();
            const container = document.getElementById('filters');
            container.innerHTML = '';
            filterOrder.forEach(key => {{
                const wrap = document.createElement('div');
                const label = document.createElement('label');
                label.textContent = key;
                const select = document.createElement('select');
                select.multiple = true;
                select.size = 6;
                select.id = `filter-${{key}}`;
                (data[key] || []).forEach(val => {{
                    const opt = document.createElement('option');
                    opt.value = val;
                    opt.textContent = val;
                    select.appendChild(opt);
                }});
                wrap.appendChild(label);
                wrap.appendChild(select);
                container.appendChild(wrap);
            }});
        }}

        function getSelections() {{
            const selections = {{}};
            filterOrder.forEach(key => {{
                const select = document.getElementById(`filter-${{key}}`);
                selections[key] = Array.from(select.selectedOptions).map(o => o.value);
            }});
            return selections;
        }}

        function renderTable(rows) {{
            const table = document.getElementById('dataTable');
            if (!rows.length) {{
                table.innerHTML = '<tr><td class="muted">No data. Choose filters and click Apply.</td></tr>';
                document.getElementById('rowInfo').textContent = '';
                return;
            }}
            const headers = Object.keys(rows[0]);
            let html = '<thead><tr>' + headers.map(h => `<th>${{h}}</th>`).join('') + '</tr></thead>';
            html += '<tbody>' + rows.map(r => '<tr>' + headers.map(h => `<td>${{r[h] ?? ''}}</td>`).join('') + '</tr>').join('') + '</tbody>';
            table.innerHTML = html;
            document.getElementById('rowInfo').textContent = `${{rows.length}} rows (showing up to {TABLE_ROW_LIMIT})`;
        }}

        function renderChart(points) {{
            const info = document.getElementById('chartInfo');
            if (!points.length) {{
                info.textContent = 'No data to plot. Choose filters and click Apply.';
                if (chart) {{ chart.destroy(); chart = null; }}
                const ctx = document.getElementById('chart').getContext('2d');
                ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
                return;
            }}
            info.textContent = `${{points.length}} points plotted`;
            const labels = points.map(p => p.timestamp);
            const values = points.map(p => p.avg);
            const ctx = document.getElementById('chart').getContext('2d');
            if (chart) chart.destroy();
            chart = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels,
                    datasets: [{{
                        label: 'Average value',
                        data: values,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56,189,248,0.15)',
                        tension: 0.25,
                        pointRadius: 3,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{ legend: {{ display: false }} }},
                    scales: {{
                        x: {{ ticks: {{ maxTicksLimit: 6 }} }},
                        y: {{ beginAtZero: false }}
                    }}
                }}
            }});
        }}

        async function applyFilters() {{
            const btn = document.getElementById('applyBtn');
            btn.disabled = true;
            btn.textContent = 'Loading...';
            const s = getSelections();
            const params = new URLSearchParams();
            ['machine_id','part_number','tool_number'].forEach(k => {{
                (s[k] || []).forEach(v => params.append(k, v));
            }});
            const res = await fetch('/api/data?' + params.toString());
            const data = await res.json();
            renderTable(data.rows);
            renderChart(data.average);
            btn.disabled = false;
            btn.textContent = 'Apply Filters';
        }}

        document.getElementById('applyBtn').addEventListener('click', applyFilters);

        loadFilters();
    </script>
</body>
</html>
                """,
        media_type="text/html",
    )


@app.get("/api/filters")
async def get_filters():
    """Return available filter values from d1."""
    payload = {}
    for col in FILTER_COLUMNS:
        if col in D1.columns:
            payload[col] = sorted(D1[col].dropna().unique().tolist())
        else:
            payload[col] = []
    return JSONResponse(payload)


@app.get("/api/data")
async def get_data(
    machine_id: Optional[List[str]] = Query(default=None),
    part_number: Optional[List[str]] = Query(default=None),
    tool_number: Optional[List[str]] = Query(default=None),
):
    """Return filtered d2 rows and average series based on d1 filter selections."""
    logger.info(
        "API /api/data called with filters m=%s p=%s t=%s",
        machine_id,
        part_number,
        tool_number,
    )

    # Require at least one filter to avoid heavy full-table responses
    if not any([machine_id, part_number, tool_number]):
        return JSONResponse({"rows": [], "average": []})

    d1_filtered = filter_d1(D1, machine_id, part_number, tool_number)
    d2_filtered = filter_d2_by_d1(D2, d1_filtered)

    # Prepare table rows (limited)
    rows = d2_filtered.head(TABLE_ROW_LIMIT).copy()
    if "timestamp" in rows.columns:
        rows["timestamp"] = rows["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    rows_out = rows.to_dict(orient="records")

    # Build average series
    avg_series = build_avg_time_series(d2_filtered)

    logger.info("Returned rows=%s avg_points=%s", len(rows_out), len(avg_series))
    return JSONResponse({"rows": rows_out, "average": avg_series})


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8500"))  # use a higher, less-contended port
    uvicorn.run("main:app", host=host, port=port, reload=False)
