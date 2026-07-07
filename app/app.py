import json
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="2MASS Galactic Midplane Browser", layout="wide")

THUMB_CSV = "thumbnails.csv"

st.title("2MASS Galactic Midplane Browser")

@st.cache_data
def load_catalog(path):
    df = pd.read_csv(path)
    required = {"l", "b", "url"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    return df

df = load_catalog(THUMB_CSV)

st.sidebar.header("Display options")
lmin = st.sidebar.number_input("l min", value=float(df["l"].min()))
lmax = st.sidebar.number_input("l max", value=float(df["l"].max()))
bmin = st.sidebar.number_input("b min", value=float(df["b"].min()))
bmax = st.sidebar.number_input("b max", value=float(df["b"].max()))

max_points = st.sidebar.slider("Max hover points", 1000, 50000, 15000, step=1000)
hover_delay = st.sidebar.slider("Hover delay [ms]", 0, 1000, 200, step=50)
switch_margin = st.sidebar.slider("Switch margin", 1.0, 2.0, 1.25, step=0.05)

sub = df.query("@lmin <= l <= @lmax and @bmin <= b <= @bmax").copy()

if len(sub) > max_points:
    sub = sub.sample(max_points, random_state=1)

points = sub[["l", "b", "url"]].to_dict(orient="records")

# Leaflet CRS.Simple uses [y, x] = [b, l].
html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<link
  rel="stylesheet"
  href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<style>
html, body {{
    margin: 0;
    padding: 0;
    height: 100%;
}}
#map {{
    width: 100%;
    height: 720px;
    background: #111;
}}
.thumb-popup {{
    width: 260px;
}}
.thumb-popup img {{
    width: 250px;
    height: auto;
    display: block;
}}
.coord-box {{
    position: absolute;
    left: 12px;
    bottom: 12px;
    z-index: 1000;
    background: rgba(255,255,255,0.85);
    padding: 5px 8px;
    font-family: sans-serif;
    font-size: 13px;
    border-radius: 4px;
}}
</style>
</head>

<body>
<div id="map"></div>
<div id="coords" class="coord-box">l, b</div>

<script>
const points = {json.dumps(points)};
const hoverDelay = {hover_delay};
const switchMargin = {switch_margin};

// Bounds are [[bmin,lmin],[bmax,lmax]]
const bounds = [[{bmin}, {lmin}], [{bmax}, {lmax}]];

const map = L.map('map', {{
    crs: L.CRS.Simple,
    minZoom: -3,
    maxZoom: 8,
    zoomSnap: 0.25,
    wheelPxPerZoomLevel: 120
}});

map.fitBounds(bounds);

// Draw coordinate bounds
L.rectangle(bounds, {{
    color: "#888",
    weight: 1,
    fill: false
}}).addTo(map);

// Invisible-ish circle markers for hover targets
const markers = [];
const layer = L.layerGroup().addTo(map);

for (const p of points) {{
    const marker = L.circleMarker([p.b, p.l], {{
        radius: 3,
        color: "#aaaaaa",
        weight: 0,
        opacity: 0.0,
        fillOpacity: 0.0
    }});

    marker.thumbUrl = p.url;
    marker.l = p.l;
    marker.b = p.b;

    marker.on("mouseover", function(e) {{
        schedulePopup(this);
    }});

    marker.addTo(layer);
    markers.push(marker);
}}

let currentMarker = null;
let currentDist2 = Infinity;
let hoverTimer = null;

function dist2(a, b) {{
    const dl = a.lng - b.l;
    const db = a.lat - b.b;
    return dl*dl + db*db;
}}

function nearestMarker(latlng) {{
    let best = null;
    let bestd2 = Infinity;

    for (const m of markers) {{
        const d2 = dist2(latlng, m);
        if (d2 < bestd2) {{
            best = m;
            bestd2 = d2;
        }}
    }}
    return [best, bestd2];
}}

function popupHtml(m) {{
    return `
      <div class="thumb-popup">
        <b>l=${{m.l.toFixed(4)}}°, b=${{m.b.toFixed(4)}}°</b><br>
        <img src="${{m.thumbUrl}}">
        <div style="font-size:11px; word-break:break-all;">${{m.thumbUrl}}</div>
      </div>
    `;
}}

function showPopup(m) {{
    currentMarker = m;
    currentDist2 = 0.0;
    L.popup({{
        autoPan: false,
        closeButton: false,
        maxWidth: 300
    }})
    .setLatLng([m.b, m.l])
    .setContent(popupHtml(m))
    .openOn(map);
}}

function schedulePopup(m) {{
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(() => showPopup(m), hoverDelay);
}}

map.on("mousemove", function(e) {{
    document.getElementById("coords").innerHTML =
        `l=${{e.latlng.lng.toFixed(4)}}°, b=${{e.latlng.lat.toFixed(4)}}°`;

    const [m, d2] = nearestMarker(e.latlng);

    if (!m) return;

    if (currentMarker === null) {{
        schedulePopup(m);
        return;
    }}

    const dCurrent = dist2(e.latlng, currentMarker);

    // Hysteresis: don't switch unless the new one is substantially closer.
    if (m !== currentMarker && dCurrent > switchMargin * d2) {{
        schedulePopup(m);
    }}
}});

map.on("mouseout", function(e) {{
    clearTimeout(hoverTimer);
}});

</script>
</body>
</html>
"""

components.html(html, height=740, scrolling=False)
