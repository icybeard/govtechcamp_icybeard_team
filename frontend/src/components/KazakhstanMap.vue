<script setup>
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

/**
 * Интерактивная карта Казахстана (области = ADM1).
 *
 * props.values — объект { 'KZ-PAV': 42, ... }: числовое значение метрики на регион,
 * по нему красится хороплет. Пустой объект — нейтральная заливка.
 * События: @region-click, @region-hover — наружу уходит { iso, name, value }.
 */
const props = defineProps({
    values: { type: Object, default: () => ({}) },
    // Точки НП: [{ id, name, lat, lon, value }] — рисуются кружками поверх областей
    points: { type: Array, default: () => [] },
    // Произвольные маркеры: [{ lat, lon, html, tooltip }] — div-иконки (стрелки ветра, очаги)
    markers: { type: Array, default: () => [] },
    // Спутниковые слои-подложки: [{ name, url, opacity, maxNativeZoom, attribution }] — переключатель Leaflet
    tileOverlays: { type: Array, default: () => [] },
    legendTitle: { type: String, default: 'Значение' },
    height: { type: String, default: '520px' }
});

const emit = defineEmits(['region-click', 'region-hover', 'point-click']);

const container = ref(null);
let map = null;
let geoLayer = null;
let pointsLayer = null;
let markersLayer = null;
let legend = null;

const PALETTE = ['#fee5d9', '#fcae91', '#fb6a4a', '#de2d26', '#a50f15'];

function colorFor(value, min, max) {
    if (value === undefined || value === null) return '#cbd5e1';
    if (max === min) return PALETTE[2];
    const t = (value - min) / (max - min);
    return PALETTE[Math.min(PALETTE.length - 1, Math.floor(t * PALETTE.length))];
}

function valueRange() {
    const nums = [...Object.values(props.values), ...props.points.map((p) => p.value)].filter((v) => typeof v === 'number');
    if (nums.length === 0) return null;
    return { min: Math.min(...nums), max: Math.max(...nums) };
}

function renderPoints() {
    if (pointsLayer) pointsLayer.remove();
    if (props.points.length === 0) return;
    const range = valueRange();
    pointsLayer = L.layerGroup(
        props.points.map((p) => {
            const marker = L.circleMarker([p.lat, p.lon], {
                radius: 6,
                weight: 1,
                color: '#334155',
                fillOpacity: 0.9,
                fillColor: range ? colorFor(p.value, range.min, range.max) : '#64748b'
            });
            marker.bindTooltip(`<strong>${p.name}</strong><br/>${props.legendTitle}: ${p.value ?? '—'}`);
            marker.on('click', () => emit('point-click', p));
            return marker;
        })
    ).addTo(map);
    const bounds = L.latLngBounds(props.points.map((p) => [p.lat, p.lon]));
    map.fitBounds(bounds, { padding: [30, 30] });
}

function renderMarkers() {
    if (markersLayer) markersLayer.remove();
    if (props.markers.length === 0) return;
    markersLayer = L.layerGroup(
        props.markers.map((m) => {
            const marker = L.marker([m.lat, m.lon], {
                icon: L.divIcon({ className: 'kz-map-divicon', html: m.html, iconSize: [24, 24], iconAnchor: [12, 12] }),
                interactive: Boolean(m.tooltip)
            });
            if (m.tooltip) marker.bindTooltip(m.tooltip);
            return marker;
        })
    ).addTo(map);
}

function styleFeature(feature) {
    const iso = feature.properties.shapeISO;
    const range = valueRange();
    return {
        weight: 1,
        color: '#475569',
        fillOpacity: 0.75,
        fillColor: range ? colorFor(props.values[iso], range.min, range.max) : '#cbd5e1'
    };
}

function regionPayload(feature) {
    return {
        iso: feature.properties.shapeISO,
        name: feature.properties.shapeName,
        value: props.values[feature.properties.shapeISO] ?? null
    };
}

function onEachFeature(feature, layer) {
    const p = regionPayload(feature);
    layer.bindTooltip(() => {
        const v = props.values[p.iso];
        return `<strong>${p.name}</strong><br/>${props.legendTitle}: ${v ?? '—'}`;
    });
    layer.on({
        click: () => emit('region-click', regionPayload(feature)),
        mouseover: (e) => {
            e.target.setStyle({ weight: 2.5, color: '#1e293b' });
            emit('region-hover', regionPayload(feature));
        },
        mouseout: (e) => geoLayer.resetStyle(e.target)
    });
}

function renderLegend() {
    if (legend) legend.remove();
    const range = valueRange();
    if (!range) return;
    legend = L.control({ position: 'bottomright' });
    legend.onAdd = () => {
        const div = L.DomUtil.create('div', 'kz-map-legend');
        const step = (range.max - range.min) / PALETTE.length;
        div.innerHTML =
            `<div class="kz-map-legend-title">${props.legendTitle}</div>` +
            PALETTE.map((c, i) => {
                const from = (range.min + step * i).toFixed(0);
                const to = (range.min + step * (i + 1)).toFixed(0);
                return `<div><i style="background:${c}"></i>${from}–${to}</div>`;
            }).join('');
        return div;
    };
    legend.addTo(map);
}

async function initMap() {
    map = L.map(container.value, { attributionControl: false }).setView([48.2, 66.9], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 12,
        opacity: 0.6
    }).addTo(map);
    L.control.attribution({ prefix: false }).addAttribution('© OpenStreetMap, geoBoundaries').addTo(map);

    if (props.tileOverlays.length) {
        const overlays = Object.fromEntries(
            props.tileOverlays.map((t) => [
                t.name,
                L.tileLayer(t.url, { opacity: t.opacity ?? 1, maxNativeZoom: t.maxNativeZoom, maxZoom: 12, attribution: t.attribution })
            ])
        );
        L.control.layers(null, overlays, { position: 'topleft', collapsed: true }).addTo(map);
    }

    const response = await fetch('/geo/kz-regions.geojson');
    const geojson = await response.json();
    geoLayer = L.geoJSON(geojson, { style: styleFeature, onEachFeature }).addTo(map);
    map.fitBounds(geoLayer.getBounds(), { padding: [10, 10] });
    renderPoints();
    renderMarkers();
    renderLegend();
}

watch(
    () => props.values,
    () => {
        if (geoLayer) {
            geoLayer.setStyle(styleFeature);
            renderLegend();
        }
    },
    { deep: true }
);

watch(
    () => props.points,
    () => {
        if (map) {
            renderPoints();
            renderLegend();
        }
    },
    { deep: true }
);

watch(
    () => props.markers,
    () => {
        if (map) renderMarkers();
    },
    { deep: true }
);

onMounted(initMap);
onBeforeUnmount(() => map?.remove());
</script>

<template>
    <div ref="container" class="kz-map rounded-lg overflow-hidden" :style="{ height }"></div>
</template>

<style>
.kz-map {
    width: 100%;
    z-index: 0;
}
.kz-map-legend {
    background: rgba(255, 255, 255, 0.92);
    color: #1e293b;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.75rem;
    line-height: 1.5;
}
.kz-map-legend-title {
    font-weight: 600;
    margin-bottom: 0.25rem;
}
.kz-map-divicon {
    background: none;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}
.kz-map-legend i {
    display: inline-block;
    width: 12px;
    height: 12px;
    margin-right: 6px;
    vertical-align: -1px;
    border-radius: 2px;
}
</style>
