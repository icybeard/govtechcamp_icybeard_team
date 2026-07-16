<script setup>
import HazardIcon from '@/components/risk/HazardIcon.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { api } from '@/service/api';
import { loadDistricts } from '@/service/geo';
import { computed, onMounted, ref } from 'vue';

const MODULE = 'flood-risk';

const loading = ref(true);
const error = ref(null);
const scores = ref([]);
const measures = ref([]);

// Сводки остальных контуров: статические JSON + кэшированный FIRMS-прокси (без ударов по квотам)
const hotspotsCount = ref(null);
const fireMl = ref(null); // { generatedAt, values }
const winterSeasons = ref({});
const districtNames = ref({}); // shapeID -> имя района

const highRisk = computed(() => scores.value.filter((s) => s.value >= 60));
const populationAtRisk = computed(() => highRisk.value.reduce((sum, s) => sum + (s.population ?? 0), 0));
const top10 = computed(() => [...scores.value].sort((a, b) => b.value - a.value).slice(0, 10));
const measureCounts = computed(() => {
    const counts = { Proposed: 0, Approved: 0, Rejected: 0, Done: 0 };
    for (const m of measures.value) counts[m.status] = (counts[m.status] ?? 0) + 1;
    return counts;
});

// Строки очереди мер: иконка + цвета чипа по статусу (пары фон/текст — из дизайн-спецификации)
const QUEUE_ROWS = [
    { key: 'Proposed', label: 'Предложено системой', icon: 'pi-clock', bg: '#fff1e6', color: '#f97316' },
    { key: 'Approved', label: 'Утверждено комиссией', icon: 'pi-check', bg: '#ecfdf3', color: '#12b76a' },
    { key: 'Rejected', label: 'Отклонено', icon: 'pi-times', bg: '#fee4e2', color: '#d92d20' },
    { key: 'Done', label: 'Выполнено', icon: 'pi-flag', bg: '#eaf2ff', color: '#2461c9' }
];

function topDistricts(valuesMap, n = 3) {
    return Object.entries(valuesMap)
        .sort((a, b) => b[1] - a[1])
        .slice(0, n)
        .map(([id, value]) => ({ name: districtNames.value[id] ?? id, value: Math.round(value) }));
}

const fireHigh = computed(() => (fireMl.value ? Object.values(fireMl.value.values).filter((v) => v >= 60).length : null));
const fireTop = computed(() => (fireMl.value ? topDistricts(fireMl.value.values) : []));

const winterLatest = computed(() => Object.keys(winterSeasons.value).sort().at(-1));
const winterValues = computed(() => {
    const season = winterSeasons.value[winterLatest.value] ?? {};
    return Object.fromEntries(Object.entries(season).map(([id, d]) => [id, d.risk]));
});
const winterHigh = computed(() => Object.values(winterValues.value).filter((v) => v >= 35).length);
const winterTop = computed(() => topDistricts(winterValues.value));

onMounted(async () => {
    try {
        const [scoreRows, measureRows] = await Promise.all([
            // period обязателен: без него API вернёт все сезоны сразу (520×18 строк)
            api.get(`/settlements/metrics/${MODULE}?metricKey=risk_score&period=2024`),
            api.get(`/measures/?module=${MODULE}`)
        ]);
        scores.value = scoreRows;
        measures.value = measureRows;
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }

    // Не блокируем страницу: сводки контуров подтягиваются независимо и молча деградируют
    loadDistricts()
        .then((list) => (districtNames.value = Object.fromEntries(list.map((d) => [d.id, d.name]))))
        .catch(() => {});
    fetch('/data/fire-ml-today.json')
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => (fireMl.value = j))
        .catch(() => {});
    fetch('/data/winter-districts.json')
        .then((r) => (r.ok ? r.json() : {}))
        .then((j) => (winterSeasons.value = j ?? {}))
        .catch(() => {});
    api.get('/fire/hotspots')
        .then((h) => (hotspotsCount.value = Array.isArray(h) ? h.length : null))
        .catch(() => {});
});
</script>

<template>
    <div class="grid grid-cols-12 gap-4">
        <!-- Заголовок страницы + CTA на ситуационную карту -->
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-start justify-between flex-wrap gap-4">
                    <div>
                        <div class="dash-title">Превентивное управление природными рисками</div>
                        <div class="dash-subtitle">Паводки (пилот: СКО) · пожары live · зима — по районам. AI предлагает — решение принимает человек.</div>
                    </div>
                    <RouterLink to="/risks" class="dash-cta">
                        <i class="pi pi-map" style="font-size: 15px"></i>
                        Ситуационная карта
                    </RouterLink>
                </div>
                <Message v-if="error" severity="error" :closable="false" class="mt-3">{{ error }}</Message>
            </div>
        </div>

        <!-- KPI-плитки -->
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="kpi-label">НП со скорами риска</div>
                <div class="kpi-value">{{ loading ? '…' : scores.length }}</div>
                <div class="kpi-sub">пилотный регион</div>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="kpi-label">Высокий риск (скор ≥ 60)</div>
                <div class="kpi-value">{{ loading ? '…' : highRisk.length }}</div>
                <div class="kpi-sub">населённых пунктов</div>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="kpi-label">Население в зоне риска</div>
                <div class="kpi-value">{{ loading ? '…' : populationAtRisk.toLocaleString('ru-RU') }}</div>
                <div class="kpi-sub">в НП со скором ≥ 60</div>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0">
                <div class="kpi-label">Мер ждёт решения</div>
                <div class="kpi-value">{{ loading ? '…' : measureCounts.Proposed }}</div>
                <div class="kpi-sub">утверждено: {{ measureCounts.Approved }}, выполнено: {{ measureCounts.Done }}</div>
            </div>
        </div>

        <!-- Сводки контуров: пожары сегодня и последняя зима -->
        <div class="col-span-12 xl:col-span-6">
            <div class="card mb-0 h-full">
                <div class="summary-head">
                    <div class="summary-head__left">
                        <span class="summary-chip" :style="{ background: RISK_HAZARDS.fire.bgColor }">
                            <HazardIcon hazard="fire" :size="17" />
                        </span>
                        <span class="summary-title">Пожары — сегодня</span>
                    </div>
                    <RouterLink to="/risks/fire" class="dash-link">Открыть →</RouterLink>
                </div>
                <div class="flex gap-9 mb-4 flex-wrap">
                    <div>
                        <div class="stat-value" :class="{ 'stat-value--empty': hotspotsCount === null }">{{ hotspotsCount ?? '—' }}</div>
                        <div class="stat-sub">активных очагов за 24 ч</div>
                    </div>
                    <div>
                        <div class="stat-value" :class="{ 'stat-value--empty': fireHigh === null }">{{ fireHigh ?? '—' }}</div>
                        <div class="stat-sub">районов с ML-прогнозом ≥ 60</div>
                    </div>
                </div>
                <template v-if="fireTop.length">
                    <div class="top-caption">Топ районов по ML-прогнозу{{ fireMl ? ` (от ${fireMl.generatedAt.slice(11, 16)} UTC)` : '' }}:</div>
                    <ul class="list-none p-0 m-0 flex flex-col">
                        <li v-for="d in fireTop" :key="d.name" class="top-row">
                            <span>{{ d.name }}</span>
                            <RiskScoreBadge :score="d.value" suffix="" size="sm" />
                        </li>
                    </ul>
                </template>
                <p v-else class="text-muted-color text-sm m-0">ML-прогноз не сгенерирован — make fire-today.</p>
            </div>
        </div>

        <div class="col-span-12 xl:col-span-6">
            <div class="card mb-0 h-full">
                <div class="summary-head">
                    <div class="summary-head__left">
                        <span class="summary-chip" :style="{ background: RISK_HAZARDS.winter.bgColor }">
                            <HazardIcon hazard="winter" :size="17" />
                        </span>
                        <span class="summary-title">Зима {{ winterLatest ? `${winterLatest - 1}–${String(winterLatest).slice(2)}` : '' }}</span>
                    </div>
                    <RouterLink to="/risks/winter" class="dash-link">Открыть →</RouterLink>
                </div>
                <div class="mb-4">
                    <div class="stat-value" :class="{ 'stat-value--empty': !winterLatest }">{{ winterLatest ? winterHigh : '—' }}</div>
                    <div class="stat-sub">районов с индексом ≥ 35</div>
                </div>
                <template v-if="winterTop.length">
                    <div class="top-caption">Топ районов по индексу зимней опасности:</div>
                    <ul class="list-none p-0 m-0 flex flex-col">
                        <li v-for="d in winterTop" :key="d.name" class="top-row">
                            <span>{{ d.name }}</span>
                            <RiskScoreBadge :score="d.value" suffix="" size="sm" />
                        </li>
                    </ul>
                </template>
                <p v-else class="text-muted-color text-sm m-0">Данные зимних сезонов не загружены.</p>
            </div>
        </div>

        <!-- Топ-10 НП по риску -->
        <div class="col-span-12 xl:col-span-7">
            <div class="card mb-0">
                <div class="dash-card-title">Топ-10 НП по риску затопления</div>
                <DataTable :value="top10" size="small" :loading="loading">
                    <Column header="#" style="width: 3rem">
                        <template #body="{ index }">
                            <span class="text-muted-color">{{ index + 1 }}</span>
                        </template>
                    </Column>
                    <Column field="name" header="Населённый пункт" />
                    <Column field="population" header="Население" style="width: 9rem">
                        <template #body="{ data }">
                            {{ data.population ? data.population.toLocaleString('ru-RU') : '—' }}
                        </template>
                    </Column>
                    <Column field="value" header="Скор" style="width: 7rem">
                        <template #body="{ data }">
                            <RiskScoreBadge :score="Math.round(data.value)" suffix="" size="sm" />
                        </template>
                    </Column>
                    <Column header="Главный фактор">
                        <template #body="{ data }">
                            <span class="factor-cell">{{ data.factors?.[0]?.name ?? '—' }}</span>
                        </template>
                    </Column>
                    <template #empty>Скоры не загружены — см. пайплайн в ml/i6-flood-risk/README.md</template>
                </DataTable>
            </div>
        </div>

        <!-- Статусы мер -->
        <div class="col-span-12 xl:col-span-5">
            <div class="card mb-0 h-full">
                <div class="dash-card-title">Очередь превентивных мер</div>
                <ul class="list-none p-0 m-0 flex flex-col gap-1 mb-4">
                    <li v-for="row in QUEUE_ROWS" :key="row.key" class="queue-row">
                        <div class="queue-row__left">
                            <span class="queue-chip" :style="{ background: row.bg, color: row.color }">
                                <i class="pi" :class="row.icon" style="font-size: 13px"></i>
                            </span>
                            <span>{{ row.label }}</span>
                        </div>
                        <span class="queue-count">{{ measureCounts[row.key] }}</span>
                    </li>
                </ul>
                <RouterLink to="/risks/flood" class="dash-outline-btn">
                    <i class="pi pi-list" style="font-size: 14px"></i>
                    К очереди мер
                </RouterLink>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* Типографика по дизайн-спецификации: заголовки 16–23px/700–800,
   числа KPI 26–28px/800, служебный текст 11–12px #98a2b3 */
.dash-title {
    font-size: 23px;
    font-weight: 800;
    margin-bottom: 8px;
}
.dash-subtitle {
    font-size: 14px;
    color: var(--text-color-secondary);
}
.dash-card-title {
    font-size: 16px;
    font-weight: 700;
    margin-bottom: 16px;
}

/* Тил-бренд ICYBEARD (#0d9488) — CTA, ссылки и вторичная кнопка */
.dash-cta {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #0d9488;
    color: #fff;
    font-size: 13px;
    font-weight: 600;
    padding: 11px 20px;
    border-radius: 10px;
    white-space: nowrap;
    transition: background 0.1s;
}
.dash-cta:hover {
    background: #0b7e73;
}
.dash-link {
    font-size: 13px;
    font-weight: 600;
    color: #0d9488;
    white-space: nowrap;
}
.dash-outline-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border: 1px solid var(--surface-border);
    border-radius: 10px;
    padding: 10px 14px;
    color: #0d9488;
    font-size: 13px;
    font-weight: 600;
    transition: background 0.1s;
}
.dash-outline-btn:hover {
    background: #f0fdfa;
}

.kpi-label {
    font-size: 13px;
    color: var(--text-color-secondary);
    margin-bottom: 10px;
}
.kpi-value {
    font-size: 28px;
    font-weight: 800;
    margin-bottom: 4px;
}
.kpi-sub {
    font-size: 12px;
    color: #98a2b3;
}

.summary-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 18px;
}
.summary-head__left {
    display: flex;
    align-items: center;
    gap: 10px;
}
.summary-chip {
    width: 34px;
    height: 34px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.summary-title {
    font-size: 16px;
    font-weight: 700;
}
.stat-value {
    font-size: 26px;
    font-weight: 800;
}
.stat-value--empty {
    color: #c6c6c0;
}
.stat-sub {
    font-size: 12px;
    color: #98a2b3;
    margin-top: 2px;
}
.top-caption {
    font-size: 12px;
    color: #98a2b3;
    margin-bottom: 6px;
}
.top-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    border-top: 1px solid var(--surface-border);
    font-size: 14px;
}

.queue-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 4px;
    font-size: 14px;
}
.queue-row__left {
    display: flex;
    align-items: center;
    gap: 10px;
}
.queue-chip {
    width: 26px;
    height: 26px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.queue-count {
    font-weight: 700;
}
.factor-cell {
    font-size: 13px;
    color: #0d9488;
}
</style>
