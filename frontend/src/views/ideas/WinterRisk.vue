<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import GranularitySwitcher from '@/components/risk/GranularitySwitcher.vue';
import LayersDatePicker from '@/components/risk/LayersDatePicker.vue';
import MapHintBadge from '@/components/risk/MapHintBadge.vue';
import MeasureExplainDialog from '@/components/risk/MeasureExplainDialog.vue';
import MeasuresQueue from '@/components/risk/MeasuresQueue.vue';
import RiskEntityCard from '@/components/risk/RiskEntityCard.vue';
import RiskHeaderCard from '@/components/risk/RiskHeaderCard.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import SeasonPicker from '@/components/risk/SeasonPicker.vue';
import { MEASURE_RULES } from '@/config/measureRules';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { api } from '@/service/api';
import { isAdmin } from '@/service/auth';
import { loadDistricts } from '@/service/geo';
import { gibsOverlays, toIsoDate } from '@/service/gibs';
import { riskSeverity } from '@/utils/riskScore';
import { useToast } from 'primevue/usetoast';
import { computed, onMounted, ref, watch } from 'vue';

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

// Слои GIBS следуют дате в пикере. Дефолт от сезона: середина февраля года Y —
// разгар зимы (Y-1)–Y; смена сезона сбрасывает дату на его дефолт.
const layerDate = ref(new Date(+season.value, 1, 15));
watch(season, (y) => (layerDate.value = new Date(+y, 1, 15)));
const tileOverlays = computed(() => gibsOverlays(toIsoDate(layerDate.value)));

const loading = ref(true);
const error = ref(null);
const allSeasons = ref({}); // { '2026': { shapeID: {risk, glaze, ...} } }
const selected = ref(null);

const seasonData = computed(() => allSeasons.value[season.value] ?? {});
const regionValues = computed(() => Object.fromEntries(Object.entries(seasonData.value).map(([id, d]) => [id, d.risk])));
const hasData = computed(() => Object.keys(regionValues.value).length > 0);

onMounted(async () => {
    loadMeasures();
    loadDistricts()
        .then((list) => (districtNames.value = Object.fromEntries(list.map((d) => [d.id, d.name]))))
        .catch(() => {});
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
        iso: region.iso,
        name: region.name,
        value: Math.round(d.risk),
        parts: SUBS.map((s) => ({ label: s.label, value: Math.round(d[s.key] ?? 0) }))
    };
}

// ── Очередь превентивных мер по районам ─────────────────────────────────────
// Скоры для генерации — risk выбранного сезона из статического JSON: районов
// в БД нет, фронт шлёт districtValues (shapeID → скор+имя) в /measures/generate.
const toast = useToast();
const measures = ref([]);
const generating = ref(false);
const districtNames = ref({}); // shapeID -> имя района (geojson)

// очередь переиспользует колонки НП: district-поля мапим в settlement-поля
const queueRows = computed(() => measures.value.map((m) => ({ ...m, settlementId: m.districtId, settlementName: m.districtName })));
const visibleMeasures = computed(() => (selected.value?.iso ? queueRows.value.filter((m) => m.settlementId === selected.value.iso) : queueRows.value));

async function loadMeasures() {
    try {
        measures.value = await api.get('/measures/?module=winter-risk');
    } catch {
        measures.value = [];
    }
}

async function generateMeasures() {
    generating.value = true;
    try {
        const districtValues = Object.fromEntries(
            Object.entries(regionValues.value)
                .filter(([id]) => districtNames.value[id])
                .map(([id, value]) => [id, { value, name: districtNames.value[id] }])
        );
        const result = await api.post('/measures/generate', { module: 'winter-risk', metricKey: 'risk_score', period: season.value, districtValues });
        toast.add({ severity: 'success', summary: `Создано черновиков: ${result.created}`, life: 4000 });
        await loadMeasures();
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Ошибка генерации', detail: e.message, life: 5000 });
    } finally {
        generating.value = false;
    }
}

async function setStatus(measure, status) {
    try {
        const updated = await api.put(`/measures/${measure.id}/status`, { status, note: null });
        measures.value = measures.value.map((m) => (m.id === updated.id ? updated : m));
    } catch (e) {
        toast.add({ severity: 'error', summary: 'Не удалось изменить статус', detail: e.message, life: 5000 });
    }
}

// Объяснимость: правило + субиндексы зимы (гололёд/метель/снегонагрузка/холод)
const explainMeasure = ref(null);
const explainVisible = ref(false);
const explainScore = computed(() => {
    const v = regionValues.value[explainMeasure.value?.settlementId];
    return v === undefined ? null : Math.round(v);
});
const explainFactors = computed(() => {
    const d = seasonData.value[explainMeasure.value?.settlementId];
    if (!d) return [];
    return SUBS.map((s) => {
        const v = Math.round(d[s.key] ?? 0);
        return { name: s.label, display: String(v), severity: riskSeverity(v) };
    });
});
function openExplain(measure) {
    explainMeasure.value = measure;
    explainVisible.value = true;
}
</script>

<template>
    <div class="grid grid-cols-12 gap-4">
        <div class="col-span-12">
            <RiskHeaderCard title="Зимний риск-скоринг" description="Индекс зимней опасности 0–100 по 174 районам (гололёд, метель, снегонагрузка, холод), ERA5-архив.">
                <template #controls>
                    <SeasonPicker v-model="season" :options="seasonOptions" />
                    <LayersDatePicker v-model="layerDate" />

                    <Tag v-if="loading" value="загрузка…" severity="secondary" />
                    <Tag v-else-if="hasData" :value="`Районов со скорами: ${Object.keys(regionValues).length}`" severity="success" />
                    <Tag v-else value="данные не загружены" severity="warn" />

                </template>
                <template #actions>
                    <GranularitySwitcher :model-value="GRANULARITY" :supports-region="true" :supports-np="false" />
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

        <div class="col-span-12">
            <MeasuresQueue :measures="visibleMeasures" entity-label="Район" :scores="regionValues" can-decide priority-hint="Приоритет = скор риска района; решение принимает комиссия" @set-status="setStatus" @explain="openExplain">
                <template #filter>
                    <Button v-if="isAdmin" label="Сгенерировать черновики мер" size="small" outlined :loading="generating" :disabled="!hasData" @click="generateMeasures" />
                    <template v-if="selected?.iso">
                        <Tag :value="`фильтр: ${selected.name}`" severity="info" />
                        <Button label="Показать все" size="small" text @click="selected = null" />
                    </template>
                </template>
                <template #empty>
                    <span v-if="selected?.iso">По району «{{ selected.name }}» мер нет — скор ниже порогов или черновики ещё не создавались.</span>
                    <span v-else>Очередь пуста — сгенерируйте черновики по скорам выбранного сезона.</span>
                </template>
            </MeasuresQueue>
        </div>

        <MeasureExplainDialog v-model:visible="explainVisible" :measure="explainMeasure" entity-label="Район" :score="explainScore" :factors="explainFactors" :rules="MEASURE_RULES['winter-risk']" priority-note="скор риска района за сезон генерации (население района не учитывается)" />
    </div>
</template>
