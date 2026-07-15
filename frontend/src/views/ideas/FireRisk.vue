<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { api } from '@/service/api';
import { gibsOverlays } from '@/service/gibs';
import { degToCompass, fetchRegionWeather, fetchWindGrid } from '@/service/weather';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

/**
 * Ситуационная live-карта пожаров: метео-индекс по областям (Open-Meteo, сейчас),
 * очаги NASA FIRMS за 24 ч, стрелки ветра, спутниковые слои GIBS.
 * Автообновление каждые 15 минут (совпадает с кэшем FIRMS-прокси).
 * Индекс — прозрачная формула (не ML): temp/35·25 + (100−RH)/100·35 + wind/40·20 + dryDays/7·20.
 */
// Раз в час: 174 района + сетка ветра ≈ 370 взвешенных запросов за обновление —
// 15-минутный интервал выжигал суточный лимит Open-Meteo за считанные часы
const REFRESH_MS = 60 * 60 * 1000;
// Районы (ADM2, 174 шт.) вместо областей — детальнее для патрулей
const GEO_URL = '/geo/kz-districts.geojson';

const loading = ref(true);
const error = ref(null);
const regionWeather = ref({});
const hotspots = ref([]);
const hotspotsError = ref(null);
const selected = ref(null);
const updatedAt = ref(null);
const windGrid = ref(null);
// Историческая частота очагов июля 2021–2025 по районам (scripts/fire_history.py):
// data-driven приор, смешивается с live-метео-индексом 50/50
const fireHistory = ref({});
// ML-прогноз на сегодня (LightGBM, ml/i9-fire-risk/fire_ml.py today) — отдельный режим карты
const mlToday = ref(null); // { generatedAt, values: {shapeID: 0-100} }
const mode = ref('composite');
const modeOptions = computed(() => [
    { label: 'Композит', value: 'composite' },
    { label: 'ML-прогноз', value: 'ml', disabled: !mlToday.value }
]);

const tileOverlays = gibsOverlays();

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
const legendTitle = computed(() => (mode.value === 'ml' ? 'ML-прогноз (P×100)' : hasHistory.value ? 'Риск (метео+история)' : 'Метео-индекс'));

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
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
                    <div>
                        <h4 class="m-0">Пожарная обстановка — live</h4>
                        <span class="text-muted-color">Риск по районам = live-метео (Open-Meteo) + историческая частота очагов (FIRMS, июль 2021–2025); очаги за 24 ч; слои GIBS. Обновление каждые 15 минут.</span>
                    </div>
                    <div class="flex items-center gap-3 flex-wrap">
                        <SelectButton v-model="mode" :options="modeOptions" optionLabel="label" optionValue="value" optionDisabled="disabled" size="small" />
                        <Tag v-if="mode === 'ml' && mlToday" :value="`прогноз от ${mlToday.generatedAt.slice(11, 16)} UTC`" severity="info" />
                        <Tag v-if="updatedAt" :value="`обновлено ${updatedAt}`" severity="success" />
                        <Tag v-if="hotspots.length" :value="`очагов за 24 ч: ${hotspots.length}`" severity="danger" />
                        <Tag v-else-if="!hotspotsError" value="очагов нет" severity="success" />
                    </div>
                </div>
                <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
                <Message v-if="hotspotsError" severity="warn" :closable="false">Очаги FIRMS: {{ hotspotsError }}</Message>
            </div>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <div class="relative">
                    <KazakhstanMap height="72vh" :geo-url="GEO_URL" :values="indexValues" :markers="markers" :tile-overlays="tileOverlays" :wind-grid="windGrid" :legend-title="legendTitle" @region-click="onRegionClick" />

                    <div v-if="!selected" style="position: absolute; top: 1rem; right: 1rem; z-index: 1000">
                        <Tag value="Кликните район — разбор метео-индекса" severity="secondary" />
                    </div>
                    <div v-else class="card m-0 shadow-lg" style="position: absolute; top: 1rem; right: 1rem; z-index: 1000; width: 340px; max-width: 85%; max-height: calc(100% - 2rem); overflow-y: auto">
                        <div class="flex items-start justify-between mb-2">
                            <h5 class="m-0">Район</h5>
                            <Button icon="pi pi-times" text rounded size="small" @click="selected = null" />
                        </div>
                        <div class="text-2xl font-medium mb-2">{{ selected.name }}</div>
                        <div class="mb-4 flex items-center gap-2 flex-wrap">
                            Риск района:
                            <Tag :value="selected.combined + ' / 100'" :severity="selected.combined > 60 ? 'danger' : selected.combined > 35 ? 'warn' : 'success'" />
                        </div>

                        <h6>Метео-индекс сейчас: {{ selected.index }}</h6>
                        <ul class="list-none p-0 m-0 flex flex-col gap-2 mb-4">
                            <li v-for="p in selected.parts" :key="p.name" class="flex items-center justify-between gap-3">
                                <span>{{ p.name }}</span>
                                <Tag :value="'+' + p.value" :severity="p.value >= 15 ? 'danger' : p.value >= 8 ? 'warn' : 'secondary'" />
                            </li>
                        </ul>

                        <div v-if="selected.ml !== undefined" class="flex items-center justify-between gap-3 mb-3">
                            <span>ML-прогноз на сегодня</span>
                            <Tag :value="selected.ml + ' / 100'" :severity="selected.ml > 60 ? 'danger' : selected.ml > 35 ? 'warn' : 'success'" />
                        </div>

                        <template v-if="selected.history">
                            <h6>История (июль 2021–2025)</h6>
                            <div class="flex items-center justify-between gap-3 mb-3">
                                <span>Очагов за 5 июлей: {{ selected.history.count.toLocaleString('ru-RU') }}</span>
                                <Tag :value="'приор ' + Math.round(selected.history.prior)" :severity="selected.history.prior > 60 ? 'danger' : selected.history.prior > 35 ? 'warn' : 'secondary'" />
                            </div>
                        </template>

                        <ul class="list-none p-0 m-0 flex flex-col gap-2 text-muted-color">
                            <li>Ветер: {{ selected.windSpeed }} км/ч, {{ degToCompass(selected.windDir) }}</li>
                            <li>Осадки: вчера {{ selected.precip24h }} мм, за 7 дней {{ selected.precip7d }} мм</li>
                        </ul>
                        <p class="text-muted-color mt-3 mb-0 text-sm">
                            {{ hasHistory ? 'Риск = 0.5·метео-сейчас + 0.5·историческая частота очагов (NASA FIRMS, лог-шкала).' : 'Метео-индекс — прозрачный baseline; история FIRMS не загружена.' }}
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
