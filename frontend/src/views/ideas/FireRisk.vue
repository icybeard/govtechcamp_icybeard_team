<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { api } from '@/service/api';
import { computed, onMounted, ref } from 'vue';

/**
 * Лайв-карта пожарной обстановки:
 *  - метео-индекс опасности по областям — Open-Meteo (без ключа), обновляется на «сейчас»;
 *  - активные очаги за 24 ч — NASA FIRMS через наш прокси (нужен FIRMS_MAP_KEY в .env);
 *  - стрелки — направление и скорость ветра в центре области.
 * Индекс — прозрачная формула (не ML): temp/35·25 + (100−RH)/100·35 + wind/40·20 + dryDays/7·20.
 */
const loading = ref(true);
const error = ref(null);
const regionWeather = ref({}); // iso -> { temp, humidity, windSpeed, windDir, precip7d, dryDays, index, parts }
const hotspots = ref([]);
const hotspotsError = ref(null);
const selected = ref(null);
const updatedAt = ref(null);

const indexValues = computed(() => Object.fromEntries(Object.entries(regionWeather.value).map(([iso, w]) => [iso, w.index])));

const markers = computed(() => [
    // Стрелки ветра в центрах областей (поворот CSS по направлению «куда дует»)
    ...Object.values(regionWeather.value).map((w) => ({
        lat: w.lat,
        lon: w.lon,
        html: `<span style="display:inline-block;transform:rotate(${w.windDir + 180}deg);font-size:18px;color:#1e293b;text-shadow:0 0 3px #fff">↑</span>`,
        tooltip: `${w.name}: ветер ${w.windSpeed} км/ч, ${degToCompass(w.windDir)}`
    })),
    // Очаги FIRMS
    ...hotspots.value.map((h) => ({
        lat: h.lat,
        lon: h.lon,
        html: '<span style="font-size:14px">🔥</span>',
        tooltip: `Очаг ${h.date} ${String(h.time).padStart(4, '0')} UTC · мощность ${h.frp} МВт (${h.satellite})`
    }))
]);

function degToCompass(deg) {
    const dirs = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];
    return dirs[Math.round(deg / 45) % 8];
}

function centroid(feature) {
    // центр bbox внешнего кольца — достаточно для стрелки ветра
    let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
    const rings = feature.geometry.type === 'MultiPolygon' ? feature.geometry.coordinates.flat(1) : feature.geometry.coordinates;
    for (const ring of rings) {
        for (const [lon, lat] of ring) {
            minLat = Math.min(minLat, lat); maxLat = Math.max(maxLat, lat);
            minLon = Math.min(minLon, lon); maxLon = Math.max(maxLon, lon);
        }
    }
    return { lat: (minLat + maxLat) / 2, lon: (minLon + maxLon) / 2 };
}

function clamp01(x) {
    return Math.max(0, Math.min(1, x));
}

function computeIndex(current, dryDays) {
    const parts = [
        { name: `Температура ${current.temperature_2m} °C`, value: Math.round(25 * clamp01(current.temperature_2m / 35)) },
        { name: `Сухость воздуха (влажность ${current.relative_humidity_2m} %)`, value: Math.round(35 * clamp01((100 - current.relative_humidity_2m) / 100)) },
        { name: `Ветер ${current.wind_speed_10m} км/ч`, value: Math.round(20 * clamp01(current.wind_speed_10m / 40)) },
        { name: `Дней без осадков: ${dryDays} из 7`, value: Math.round(20 * clamp01(dryDays / 7)) }
    ];
    return { index: parts.reduce((s, p) => s + p.value, 0), parts };
}

onMounted(async () => {
    try {
        const geo = await (await fetch('/geo/kz-regions.geojson')).json();
        const regions = geo.features.map((f) => ({ iso: f.properties.shapeISO, name: f.properties.shapeName, ...centroid(f) }));

        const params = new URLSearchParams({
            latitude: regions.map((r) => r.lat.toFixed(3)).join(','),
            longitude: regions.map((r) => r.lon.toFixed(3)).join(','),
            current: 'temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m',
            daily: 'precipitation_sum',
            past_days: '7',
            forecast_days: '1',
            timezone: 'UTC'
        });
        const weather = await (await fetch(`https://api.open-meteo.com/v1/forecast?${params}`)).json();

        const result = {};
        weather.forEach((w, i) => {
            const precipDays = w.daily.precipitation_sum.slice(0, 7);
            const precip7d = precipDays.reduce((s, v) => s + (v ?? 0), 0);
            let dryDays = 0;
            for (let d = precipDays.length - 1; d >= 0 && (precipDays[d] ?? 0) < 1; d--) dryDays++;
            const { index, parts } = computeIndex(w.current, dryDays);
            result[regions[i].iso] = {
                ...regions[i],
                temp: w.current.temperature_2m,
                humidity: w.current.relative_humidity_2m,
                windSpeed: w.current.wind_speed_10m,
                windDir: w.current.wind_direction_10m,
                precip7d: Math.round(precip7d * 10) / 10,
                dryDays,
                index,
                parts
            };
        });
        regionWeather.value = result;
        updatedAt.value = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        error.value = `Open-Meteo недоступен: ${e.message}`;
    }

    try {
        hotspots.value = await api.get('/fire/hotspots');
    } catch (e) {
        hotspotsError.value = e.message;
    } finally {
        loading.value = false;
    }
});

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
                        <span class="text-muted-color">Метео-индекс опасности (Open-Meteo, сейчас) + активные очаги NASA FIRMS за 24 ч. Стрелки — куда дует ветер.</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <Tag v-if="updatedAt" :value="`погода на ${updatedAt}`" severity="success" />
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
                <KazakhstanMap :values="indexValues" :markers="markers" legend-title="Метео-индекс" @region-click="onRegionClick" />
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
                        <li>Осадки за 7 дней: {{ selected.precip7d }} мм</li>
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
