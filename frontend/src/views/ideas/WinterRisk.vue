<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import GranularitySwitcher from '@/components/risk/GranularitySwitcher.vue';
import MapHintBadge from '@/components/risk/MapHintBadge.vue';
import RiskEntityCard from '@/components/risk/RiskEntityCard.vue';
import RiskHeaderCard from '@/components/risk/RiskHeaderCard.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import SeasonPicker from '@/components/risk/SeasonPicker.vue';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { gibsOverlays } from '@/service/gibs';
import { riskSeverity } from '@/utils/riskScore';
import { computed, onMounted, ref } from 'vue';

// Зимняя обстановка ПО РАЙОНАМ (ADM2, 174). Данные готовит scripts/winter_fetch_districts.py
// (один раз) в frontend/public/data/winter-districts.json — страница читает статический файл,
// БД не участвует. Индекс 0–100 = 0.30·гололёд + 0.30·метель + 0.20·снегонагрузка + 0.20·холод.
const GEO_URL = '/geo/kz-districts.geojson';
const CURRENT = '2026'; // последняя завершённая зима 2025–26
const BLUE = ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'];
const HAZARD = RISK_HAZARDS.winter;

// Скоринг зимы есть только на уровне района — «Населённый пункт»
// в GranularitySwitcher заблокирован (как в макете), пока нет модели по НП.
const GRANULARITY = 'region';

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

// Слои GIBS следуют выбранному сезону: середина февраля года Y — разгар зимы (Y-1)–Y,
// снежный покров и снимок показывают именно ту зиму
const tileOverlays = computed(() => gibsOverlays(`${season.value}-02-15`));

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
    <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12">
            <RiskHeaderCard title="Зимний риск-скоринг" description="Индекс зимней опасности 0–100 по 174 районам (гололёд, метель, снегонагрузка, холод), ERA5-архив.">
                <template #controls>
                    <SeasonPicker v-model="season" :options="seasonOptions" />

                    <Tag v-if="loading" value="загрузка…" severity="secondary" />
                    <Tag v-else-if="hasData" :value="`Районов со скорами: ${Object.keys(regionValues).length}`" severity="success" />
                    <Tag v-else value="данные не загружены" severity="warn" />

                    <div style="margin-left: auto">
                        <GranularitySwitcher :model-value="GRANULARITY" :supports-region="true" :supports-np="false" />
                    </div>
                </template>
                <template #messages>
                    <Message v-if="error" severity="error" :closable="false" class="mt-4">{{ error }}</Message>
                    <Message v-else-if="!loading && !hasData" severity="info" :closable="false" class="mt-4">
                        Данные не сгенерированы: <code>python3 scripts/winter_fetch_districts.py</code> (один раз, ~3 минуты) — файл попадёт в сборку фронтенда.
                    </Message>
                </template>
            </RiskHeaderCard>
        </div>

        <div class="col-span-12">
            <div class="card mb-0">
                <!-- isolate: свой контекст наложения — карточка объекта и подсказка (z-index 1000)
                     не всплывают над фиксированным топбаром при прокрутке -->
                <div class="relative isolate">
                    <!-- 600px — высота основной карты по дизайн-спецификации -->
                    <KazakhstanMap height="600px" :geo-url="GEO_URL" :values="regionValues" :palette="BLUE" :domain-min="0" :domain-max="100" :tile-overlays="tileOverlays" legend-title="Зимний риск" @region-click="onRegionClick" />

                    <MapHintBadge v-if="!selected" text="Кликните район — скор, факторы «почему» и меры" />
                    <RiskEntityCard v-else entity-label="Район" :name="selected.name" :color="HAZARD.color" @close="selected = null">
                        <div class="risk-meta-row mb-4">
                            Риск района ({{ seasonOptions.find((o) => o.value === season)?.label }}):
                            <RiskScoreBadge :score="selected.value" />
                        </div>

                        <div class="risk-section-title">Из чего складывается (0–100 по каждому)</div>
                        <ul class="list-none p-0 m-0 flex flex-col gap-2 mb-3">
                            <li v-for="p in selected.parts" :key="p.label" class="risk-metric-row">
                                <span class="risk-metric-label">{{ p.label }}</span>
                                <Tag :value="p.value" :severity="riskSeverity(p.value)" />
                            </li>
                        </ul>
                        <p class="risk-footnote mb-0">Итог — взвешенный композит: гололёд 0.30 + метель 0.30 + снегонагрузка 0.20 + холод 0.20.</p>
                    </RiskEntityCard>
                </div>
            </div>
        </div>

    </div>
</template>
