<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { gibsOverlays } from '@/service/gibs';
import { computed, onMounted, ref } from 'vue';

// Зимняя обстановка ПО РАЙОНАМ (ADM2, 174). Данные готовит scripts/winter_fetch_districts.py
// (один раз) в frontend/public/data/winter-districts.json — страница читает статический файл,
// БД не участвует. Индекс 0–100 = 0.30·гололёд + 0.30·метель + 0.20·снегонагрузка + 0.20·холод.
const GEO_URL = '/geo/kz-districts.geojson';
const CURRENT = '2026'; // последняя завершённая зима 2025–26
const BLUE = ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'];

const SUBS = [
    { key: 'glaze', label: 'Гололёд' },
    { key: 'blizzard', label: 'Метель/заносы' },
    { key: 'snowload', label: 'Снеговая нагрузка' },
    { key: 'cold', label: 'Холод' }
];

const season = ref(CURRENT);
const seasonOptions = Array.from({ length: 7 }, (_, i) => String(2026 - i)).map((y) => ({
    label: y === CURRENT ? `зима ${+y - 1}–${y.slice(2)} (последняя)` : `зима ${+y - 1}–${y.slice(2)}`,
    value: y
}));

const tileOverlays = gibsOverlays(); // снежный покров/снимок — те же слои GIBS

const loading = ref(true);
const error = ref(null);
const allSeasons = ref({}); // { '2026': { shapeID: {risk, glaze, ...} } }
const selected = ref(null);

const seasonData = computed(() => allSeasons.value[season.value] ?? {});
const regionValues = computed(() => Object.fromEntries(Object.entries(seasonData.value).map(([id, d]) => [id, d.risk])));
const hasData = computed(() => Object.keys(regionValues.value).length > 0);

onMounted(async () => {
    try {
        const response = await fetch('/data/winter-districts.json');
        if (!response.ok) throw new Error('winter-districts.json не найден');
        allSeasons.value = await response.json();
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }
});

function sev(v) {
    return v > 60 ? 'danger' : v > 35 ? 'warn' : 'success';
}

function onRegionClick(region) {
    const d = seasonData.value[region.iso];
    if (!d) {
        selected.value = null;
        return;
    }
    selected.value = {
        name: region.name,
        value: Math.round(d.risk),
        parts: SUBS.map((s) => ({ label: s.label, value: Math.round(d[s.key] ?? 0) }))
    };
}
</script>

<template>
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
                    <div>
                        <h4 class="m-0">Зимняя обстановка — риск-скоринг по районам</h4>
                        <span class="text-muted-color">Индекс зимней опасности 0–100 по 174 районам (гололёд, метель, снегонагрузка, холод), ERA5-архив.</span>
                    </div>
                    <div class="flex items-center gap-3 flex-wrap">
                        <div class="flex items-center gap-2">
                            <label for="seasonSelect" class="text-muted-color">Сезон</label>
                            <Select v-model="season" inputId="seasonSelect" :options="seasonOptions" optionLabel="label" optionValue="value" size="small" />
                        </div>
                        <Tag v-if="loading" value="загрузка…" severity="secondary" />
                        <Tag v-else-if="hasData" :value="`районов: ${Object.keys(regionValues).length}`" severity="success" />
                        <Tag v-else value="данные не загружены" severity="warn" />
                    </div>
                </div>
                <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
                <Message v-else-if="!loading && !hasData" severity="info" :closable="false">
                    Данные не сгенерированы: <code>python3 scripts/winter_fetch_districts.py</code> (один раз, ~3 минуты) — файл попадёт в сборку фронтенда.
                </Message>
            </div>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <div class="relative">
                    <KazakhstanMap height="72vh" :geo-url="GEO_URL" :values="regionValues" :palette="BLUE" :domain-min="0" :domain-max="100" :tile-overlays="tileOverlays" legend-title="Индекс зимней опасности" @region-click="onRegionClick" />

                    <div v-if="!selected" style="position: absolute; top: 1rem; right: 1rem; z-index: 1000">
                        <Tag value="Кликните район — скор и разбор по факторам" severity="secondary" />
                    </div>
                    <div v-else class="card m-0 shadow-lg" style="position: absolute; top: 1rem; right: 1rem; z-index: 1000; width: 330px; max-width: 85%">
                        <div class="flex items-start justify-between mb-2">
                            <h5 class="m-0">Район</h5>
                            <Button icon="pi pi-times" text rounded size="small" @click="selected = null" />
                        </div>
                        <div class="text-2xl font-medium mb-2">{{ selected.name }}</div>
                        <div class="mb-4">
                            Индекс зимней опасности ({{ seasonOptions.find((o) => o.value === season)?.label }}):
                            <Tag :value="selected.value + ' / 100'" :severity="sev(selected.value)" />
                        </div>

                        <h6>Из чего складывается (0–100 по каждому)</h6>
                        <ul class="list-none p-0 m-0 flex flex-col gap-2 mb-3">
                            <li v-for="p in selected.parts" :key="p.label" class="flex items-center justify-between gap-3">
                                <span>{{ p.label }}</span>
                                <Tag :value="p.value" :severity="sev(p.value)" />
                            </li>
                        </ul>
                        <p class="text-muted-color mb-0 text-sm">Итог — взвешенный композит: гололёд 0.30 + метель 0.30 + снегонагрузка 0.20 + холод 0.20.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
