<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { api } from '@/service/api';
import { gibsOverlays } from '@/service/gibs';
import { degToCompass, fetchRegionWeather, windMarkers } from '@/service/weather';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

/**
 * Ситуационная live-карта пожаров: метео-индекс по областям (Open-Meteo, сейчас),
 * очаги NASA FIRMS за 24 ч, стрелки ветра, спутниковые слои GIBS.
 * Автообновление каждые 15 минут (совпадает с кэшем FIRMS-прокси).
 * Индекс — прозрачная формула (не ML): temp/35·25 + (100−RH)/100·35 + wind/40·20 + dryDays/7·20.
 */
const REFRESH_MS = 15 * 60 * 1000;

const loading = ref(true);
const error = ref(null);
const regionWeather = ref({});
const hotspots = ref([]);
const hotspotsError = ref(null);
const selected = ref(null);
const updatedAt = ref(null);

const tileOverlays = gibsOverlays();

const indexValues = computed(() => Object.fromEntries(Object.entries(regionWeather.value).map(([iso, w]) => [iso, w.index])));

const markers = computed(() => [
    ...windMarkers(regionWeather.value, (w) => `${w.name}: ветер ${w.windSpeed} км/ч, ${degToCompass(w.windDir)}; осадки 24ч ${w.precip24h} мм`),
    ...hotspots.value.map((h) => ({
        lat: h.lat,
        lon: h.lon,
        html: '<span style="font-size:14px">🔥</span>',
        tooltip: `Очаг ${h.date} ${String(h.time).padStart(4, '0')} UTC · мощность ${h.frp} МВт (${h.satellite})`
    }))
]);

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
        const { updatedAt: at, regions } = await fetchRegionWeather();
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
}

let timer = null;
onMounted(() => {
    refresh();
    timer = setInterval(refresh, REFRESH_MS);
});
onBeforeUnmount(() => clearInterval(timer));

function onRegionClick(region) {
    selected.value = regionWeather.value[region.iso] ?? null;
}
</script>

<template>
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
                    <div>
                        <h4 class="m-0">И-9. Пожарная обстановка — live</h4>
                        <span class="text-muted-color">Метео-индекс (Open-Meteo, сейчас) + очаги NASA FIRMS за 24 ч + слои GIBS. Обновление каждые 15 минут.</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <Tag v-if="updatedAt" :value="`обновлено ${updatedAt}`" severity="success" />
                        <Tag v-if="hotspots.length" :value="`очагов за 24 ч: ${hotspots.length}`" severity="danger" />
                        <Tag v-else-if="!hotspotsError" value="очагов нет" severity="success" />
                    </div>
                </div>
                <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
                <Message v-if="hotspotsError" severity="warn" :closable="false">Очаги FIRMS: {{ hotspotsError }}</Message>
            </div>
        </div>

        <div class="col-span-12 lg:col-span-8">
            <div class="card mb-0">
                <KazakhstanMap :values="indexValues" :markers="markers" :tile-overlays="tileOverlays" legend-title="Метео-индекс" @region-click="onRegionClick" />
            </div>
        </div>

        <div class="col-span-12 lg:col-span-4">
            <div class="card mb-0 h-full">
                <h5>Область</h5>
                <template v-if="selected">
                    <div class="text-2xl font-medium mb-2">{{ selected.name }}</div>
                    <div class="mb-4">
                        Метео-индекс:
                        <Tag :value="selected.index + ' / 100'" :severity="selected.index > 60 ? 'danger' : selected.index > 35 ? 'warn' : 'success'" />
                    </div>

                    <h6>Из чего складывается</h6>
                    <ul class="list-none p-0 m-0 flex flex-col gap-2 mb-4">
                        <li v-for="p in selected.parts" :key="p.name" class="flex items-center justify-between gap-3">
                            <span>{{ p.name }}</span>
                            <Tag :value="'+' + p.value" :severity="p.value >= 15 ? 'danger' : p.value >= 8 ? 'warn' : 'secondary'" />
                        </li>
                    </ul>

                    <ul class="list-none p-0 m-0 flex flex-col gap-2 text-muted-color">
                        <li>Ветер: {{ selected.windSpeed }} км/ч, {{ degToCompass(selected.windDir) }}</li>
                        <li>Осадки: вчера {{ selected.precip24h }} мм, за 7 дней {{ selected.precip7d }} мм</li>
                    </ul>
                </template>
                <p v-else class="text-muted-color">Кликните область — здесь появится разбор метео-индекса: температура, сухость, ветер, дни без осадков.</p>

                <template v-if="!loading">
                    <h6 class="mt-4">Дальше по плану</h6>
                    <p class="text-muted-color m-0">
                        ML-прогноз на завтра по ячейкам 10×10 км (FIRMS 2001–2026 + ERA5 + NDVI) и очередь патрулей — см.
                        docs/ideas/i9-fire-risk/. Метео-индекс выше — прозрачный baseline этой модели.
                    </p>
                </template>
            </div>
        </div>
    </div>
</template>
