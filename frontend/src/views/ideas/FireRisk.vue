<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import GranularitySwitcher from '@/components/risk/GranularitySwitcher.vue';
import MapHintBadge from '@/components/risk/MapHintBadge.vue';
import RiskEntityCard from '@/components/risk/RiskEntityCard.vue';
import RiskHeaderCard from '@/components/risk/RiskHeaderCard.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { api } from '@/service/api';
import LayersDatePicker from '@/components/risk/LayersDatePicker.vue';
import { gibsOverlays, toIsoDate } from '@/service/gibs';
import { degToCompass, fetchRegionWeather, fetchWindGrid } from '@/service/weather';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

/**
 * Риск-скоринг природных пожаров: метео-индекс по районам (Open-Meteo, сейчас) +
 * историческая частота очагов NASA FIRMS; очаги за 24 ч; спутниковые слои GIBS.
 * Автообновление раз в час (бережём суточный лимит Open-Meteo).
 * ML-прогноз на сегодня (LightGBM) показывается в карточке района.
 */
// Раз в час: 174 района + сетка ветра ≈ 370 взвешенных запросов за обновление —
// 15-минутный интервал выжигал суточный лимит Open-Meteo за считанные часы
const REFRESH_MS = 60 * 60 * 1000;
// Районы (ADM2, 174 шт.) вместо областей — детальнее для патрулей
const GEO_URL = '/geo/kz-districts.geojson';
const HAZARD = RISK_HAZARDS.fire;

// Скоринг пожаров есть только на уровне района — «Населённый пункт»
// в GranularitySwitcher заблокирован (как в макете), пока нет модели по НП.
const GRANULARITY = 'region';

const loading = ref(true);
const error = ref(null);
const regionWeather = ref({});
const hotspots = ref([]);
const hotspotsError = ref(null);
const selected = ref(null);
const updatedAt = ref(null);
const windGrid = ref(null);
// Live-погода поверх карты: анимация частиц ветра. Сам скор тоже метео-live,
// тумблер управляет только визуальным слоем ветра.
const liveWeather = ref(true);
// Историческая частота очагов июля 2021–2025 по районам (scripts/fire_history.py):
// data-driven приор, смешивается с live-метео-индексом 50/50
const fireHistory = ref({});
// ML-прогноз на сегодня (LightGBM, ml/i9-fire-risk/fire_ml.py today) —
// отдельный режим карты + строка в карточке района
const mlToday = ref(null); // { generatedAt, values: {shapeID: 0-100} }
const mode = ref('composite');
const modeOptions = computed(() => [
    { label: 'Композит', value: 'composite' },
    { label: 'ML-прогноз', value: 'ml', disabled: !mlToday.value }
]);

// Дата слоёв GIBS: дефолт «вчера» (live-режим — IMERG «последний срез»);
// выбор другой даты в пикере переключает слои на архивный срез
const layerDate = ref(new Date(Date.now() - 24 * 3600 * 1000));
const tileOverlays = computed(() => {
    const iso = toIsoDate(layerDate.value);
    return iso === toIsoDate(new Date(Date.now() - 24 * 3600 * 1000)) ? gibsOverlays() : gibsOverlays(iso);
});

// Итоговый риск района = 0.5·метео-сейчас + 0.5·историческая частота (если история загружена)
const hasHistory = computed(() => Object.keys(fireHistory.value).length > 0);
const compositeValues = computed(() =>
    Object.fromEntries(
        Object.entries(regionWeather.value).map(([iso, w]) => {
            const prior = fireHistory.value[iso]?.prior;
            return [iso, prior === undefined ? w.index : Math.round(0.5 * w.index + 0.5 * prior)];
        })
    )
);
const indexValues = computed(() => (mode.value === 'ml' && mlToday.value ? mlToday.value.values : compositeValues.value));
const legendTitle = computed(() => (mode.value === 'ml' ? 'ML-прогноз (P×100)' : hasHistory.value ? 'Риск пожара' : 'Метео-индекс'));
const scoredCount = computed(() => Object.keys(indexValues.value).length);

// стрелки по 174 районам были бы кашей — ветер показывает анимация частиц
const markers = computed(() =>
    hotspots.value.map((h) => ({
        lat: h.lat,
        lon: h.lon,
        html: '<span style="font-size:14px">🔥</span>',
        tooltip: `Очаг ${h.date} ${String(h.time).padStart(4, '0')} UTC · мощность ${h.frp} МВт (${h.satellite})`
    }))
);

function clamp01(x) {
    return Math.max(0, Math.min(1, x));
}

function computeIndex(w) {
    const parts = [
        { name: `Температура ${w.temp} °C`, value: Math.round(25 * clamp01(w.temp / 35)) },
        { name: `Сухость воздуха (влажность ${w.humidity} %)`, value: Math.round(35 * clamp01((100 - w.humidity) / 100)) },
        { name: `Ветер ${w.windSpeed} км/ч`, value: Math.round(20 * clamp01(w.windSpeed / 40)) },
        { name: `Дней без осадков: ${w.dryDays} из 7`, value: Math.round(20 * clamp01(w.dryDays / 7)) }
    ];
    return { index: parts.reduce((s, p) => s + p.value, 0), parts };
}

async function refresh() {
    try {
        const { updatedAt: at, regions } = await fetchRegionWeather(GEO_URL);
        for (const w of Object.values(regions)) Object.assign(w, computeIndex(w));
        regionWeather.value = regions;
        updatedAt.value = at;
        error.value = null;
    } catch (e) {
        error.value = `Open-Meteo недоступен: ${e.message}`;
    }
    try {
        hotspots.value = await api.get('/fire/hotspots');
        hotspotsError.value = null;
    } catch (e) {
        hotspotsError.value = e.message;
    } finally {
        loading.value = false;
    }
    try {
        windGrid.value = await fetchWindGrid(); // анимация частиц ветра
    } catch {
        windGrid.value = null;
    }
}

let timer = null;
onMounted(async () => {
    try {
        const response = await fetch('/data/fire-history.json');
        if (response.ok) fireHistory.value = await response.json();
    } catch {
        /* без истории работаем на чистом метео-индексе */
    }
    try {
        const response = await fetch('/data/fire-ml-today.json');
        if (response.ok) mlToday.value = await response.json();
    } catch {
        /* режим ML недоступен — селектор задизейблен */
    }
    refresh();
    timer = setInterval(refresh, REFRESH_MS);
});
onBeforeUnmount(() => clearInterval(timer));

function onRegionClick(region) {
    const w = regionWeather.value[region.iso];
    if (!w) {
        selected.value = null;
        return;
    }
    const history = fireHistory.value[region.iso];
    selected.value = { ...w, combined: compositeValues.value[region.iso], history, ml: mlToday.value?.values?.[region.iso] };
}
</script>

<template>
    <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12">
            <RiskHeaderCard title="Риск-скоринг природных пожаров" description="Риск возникновения очагов возгорания по метеоданным (Open-Meteo) и истории NASA FIRMS. Все районы Казахстана, очаги за 24 ч, обновление раз в час.">
                <template #controls>
                    <SelectButton v-model="mode" :options="modeOptions" optionLabel="label" optionValue="value" optionDisabled="disabled" size="small" />
                    <Tag v-if="mode === 'ml' && mlToday" :value="`прогноз от ${mlToday.generatedAt.slice(11, 16)} UTC`" severity="info" />
                    <LayersDatePicker v-model="layerDate" />

                    <div class="flex items-center gap-2">
                        <ToggleSwitch v-model="liveWeather" inputId="fireLiveWeather" />
                        <label for="fireLiveWeather" class="text-muted-color">Live-погода</label>
                    </div>

                    <Tag v-if="updatedAt" :value="`обновлено ${updatedAt}`" severity="success" />
                    <Tag v-if="scoredCount" :value="`Районов со скорами: ${scoredCount}`" severity="success" />
                    <Tag v-if="hotspots.length" :value="`очагов за 24 ч: ${hotspots.length}`" severity="danger" />
                    <Tag v-else-if="!hotspotsError" value="очагов нет" severity="success" />

                    <div style="margin-left: auto">
                        <GranularitySwitcher :model-value="GRANULARITY" :supports-region="true" :supports-np="false" />
                    </div>
                </template>
                <template #messages>
                    <Message v-if="error" severity="error" :closable="false" class="mt-4">{{ error }}</Message>
                    <Message v-if="hotspotsError" severity="warn" :closable="false" class="mt-4">Очаги FIRMS: {{ hotspotsError }}</Message>
                </template>
            </RiskHeaderCard>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <!-- isolate: свой контекст наложения — карточка объекта и подсказка (z-index 1000)
                     не всплывают над фиксированным топбаром при прокрутке -->
                <div class="relative isolate">
                    <!-- 600px — высота основной карты по дизайн-спецификации -->
                    <KazakhstanMap height="600px" :geo-url="GEO_URL" :values="indexValues" :markers="markers" :tile-overlays="tileOverlays" :wind-grid="liveWeather ? windGrid : null" :legend-title="legendTitle" @region-click="onRegionClick" />

                    <MapHintBadge v-if="!selected" text="Кликните район — скор, факторы «почему» и меры" />
                    <RiskEntityCard v-else entity-label="Район" :name="selected.name" :color="HAZARD.color" @close="selected = null">
                        <div class="risk-meta-row mb-4">
                            Риск района:
                            <RiskScoreBadge :score="selected.combined" />
                        </div>

                        <div class="risk-section-title">Метео-индекс сейчас: {{ selected.index }}</div>
                        <ul class="list-none p-0 m-0 flex flex-col gap-2 mb-4">
                            <li v-for="p in selected.parts" :key="p.name" class="risk-metric-row">
                                <span class="risk-metric-label">{{ p.name }}</span>
                                <Tag :value="'+' + p.value" :severity="p.value >= 15 ? 'danger' : p.value >= 8 ? 'warn' : 'secondary'" />
                            </li>
                        </ul>

                        <div v-if="selected.ml !== undefined" class="risk-metric-row mb-3">
                            <span class="risk-metric-label">ML-прогноз на сегодня</span>
                            <RiskScoreBadge :score="selected.ml" />
                        </div>

                        <template v-if="selected.history">
                            <div class="risk-section-title">История (июль 2021–2025)</div>
                            <div class="risk-metric-row mb-3">
                                <span class="risk-metric-label">Очагов за 5 июлей: {{ selected.history.count.toLocaleString('ru-RU') }}</span>
                                <Tag :value="'приор ' + Math.round(selected.history.prior)" :severity="selected.history.prior > 60 ? 'danger' : selected.history.prior > 35 ? 'warn' : 'secondary'" />
                            </div>
                        </template>

                        <ul class="list-none p-0 m-0 flex flex-col gap-1">
                            <li class="risk-footnote">Ветер: {{ selected.windSpeed }} км/ч, {{ degToCompass(selected.windDir) }}</li>
                            <li class="risk-footnote">Осадки: вчера {{ selected.precip24h }} мм, за 7 дней {{ selected.precip7d }} мм</li>
                        </ul>
                        <p class="risk-footnote mt-3 mb-0">
                            {{ hasHistory ? 'Риск = 0.5·метео-сейчас + 0.5·историческая частота очагов (NASA FIRMS, лог-шкала).' : 'Метео-индекс — прозрачный baseline; история FIRMS не загружена.' }}
                        </p>
                    </RiskEntityCard>
                </div>
            </div>
        </div>
    </div>
</template>
