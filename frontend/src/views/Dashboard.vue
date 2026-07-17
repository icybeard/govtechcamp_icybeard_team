<script setup>
import HazardIcon from '@/components/risk/HazardIcon.vue';
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import { MEASURE_STATUS } from '@/config/measureStatus';
import { RISK_HAZARDS } from '@/config/riskHazards';
import { api } from '@/service/api';
import { loadDistricts } from '@/service/geo';
import { ruDistrictName } from '@/utils/districtNames';
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

const FLOOD_MODULE = 'flood-risk';
// Меры считаем по всем контурам: после появления районных мер у пожаров и зимы
// комиссия видит на дашборде общую очередь, а не только паводковую
const RISK_MODULES = ['flood-risk', 'fire-risk', 'winter-risk'];

const loading = ref(true);
const error = ref(null);
const scores = ref([]);
const measures = ref([]);

// Сводки остальных контуров: статические JSON + кэшированный FIRMS-прокси (без ударов по квотам)
const hotspotsCount = ref(null);
const fireMl = ref(null); // { generatedAt, values }
const winterSeasons = ref({});
const districtNames = ref({}); // shapeID -> имя района

// Разбивка очереди мер по контурам — чипы-ссылки в карточке очереди
const MODULE_HAZARD = { 'flood-risk': 'flood', 'fire-risk': 'fire', 'winter-risk': 'winter' };
const measuresByModule = computed(() => {
    const counts = {};
    for (const m of measures.value) counts[m.module] = (counts[m.module] ?? 0) + 1;
    return counts;
});
const hasModuleInfo = computed(() => measures.value.some((m) => m.module));

// Последние решения комиссии — 5 свежих мер не в статусе «Предложено»
const recentDecisions = computed(() =>
    measures.value
        .filter((m) => m.status !== 'Proposed' && m.decidedAt)
        .sort((a, b) => new Date(b.decidedAt) - new Date(a.decidedAt))
        .slice(0, 5)
);

// Входящие для комиссии: топ ожидающих мер со всех контуров. Шкалы приоритета
// у контуров разные (паводки: скор×lg(население) — до ~550; районы: скор ≤100),
// поэтому сортируем по приоритету, нормированному к максимуму своего контура —
// иначе паводки всегда вытесняли бы районные меры из топа.
const pendingTop = computed(() => {
    const pending = measures.value.filter((m) => m.status === 'Proposed');
    const maxByModule = {};
    for (const m of pending) maxByModule[m.module] = Math.max(maxByModule[m.module] ?? 0, m.priority ?? 0);
    return pending
        .map((m) => ({ ...m, relPriority: (m.priority ?? 0) / (maxByModule[m.module] || 1) }))
        .sort((a, b) => b.relPriority - a.relPriority)
        .slice(0, 5);
});

// Имя объекта меры: у паводков — НП (settlementName), у пожаров/зимы — район.
// settlementName у районных мер — пустая строка (не null), поэтому «||», не «??»
const measureName = (m) => ruDistrictName(m.settlementName || m.districtName || '');

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

const router = useRouter();

function topDistricts(valuesMap, n = 3) {
    return Object.entries(valuesMap)
        .sort((a, b) => b[1] - a[1])
        .slice(0, n)
        .map(([id, value]) => ({ id, name: ruDistrictName(districtNames.value[id] ?? id), value: Math.round(value) }));
}

// Deep-links из топ-списков: открыть вкладку угрозы с уже выбранным объектом
function openSettlement(row) {
    router.push({ path: '/risks', query: { mode: 'flood', settlement: row.settlementId } });
}
function openDistrict(mode, id) {
    router.push({ path: '/risks', query: { mode, district: id } });
}

const fireHigh = computed(() => (fireMl.value ? Object.values(fireMl.value.values).filter((v) => v >= 60).length : null));
const fireCritical = computed(() => (fireMl.value ? Object.values(fireMl.value.values).filter((v) => v >= 80).length : null));
const fireTop = computed(() => (fireMl.value ? topDistricts(fireMl.value.values) : []));

// Зимний ML (winter-ml-seasons.json): районов с вероятностью опасного дня ≥10%
// за последнюю зиму — вторая цифра зимней карточки («—», если витрины нет)
const winterMl = ref(null);
const winterMlHigh = computed(() => {
    const latest = winterMl.value?.[Object.keys(winterMl.value ?? {}).sort().at(-1)];
    return latest ? Object.values(latest).filter((d) => d.proba >= 10).length : null;
});

const winterLatest = computed(() => Object.keys(winterSeasons.value).sort().at(-1));
const winterValues = computed(() => {
    const season = winterSeasons.value[winterLatest.value] ?? {};
    return Object.fromEntries(Object.entries(season).map(([id, d]) => [id, d.risk]));
});
const winterHigh = computed(() => Object.values(winterValues.value).filter((v) => v >= 35).length);
const winterSevere = computed(() => Object.values(winterValues.value).filter((v) => v >= 60).length);
const winterTop = computed(() => topDistricts(winterValues.value));

onMounted(async () => {
    try {
        const [scoreRows, ...measureLists] = await Promise.all([
            // period обязателен: без него API вернёт все сезоны сразу (520×18 строк)
            api.get(`/settlements/metrics/${FLOOD_MODULE}?metricKey=risk_score&period=2024`),
            ...RISK_MODULES.map((module) => api.get(`/measures/?module=${module}`))
        ]);
        scores.value = scoreRows;
        measures.value = measureLists.flat();
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
    fetch('/data/winter-ml-seasons.json')
        .then((r) => (r.ok ? r.json() : null))
        .then((j) => (winterMl.value = j))
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

        <!-- KPI-плитки: только агрегаты, не дублирующие карточки контуров ниже -->
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0 h-full">
                <div class="kpi-label">Под мониторингом</div>
                <div class="kpi-value">{{ loading ? '…' : scores.length }} НП</div>
                <div class="kpi-sub">паводки (пилот СКО) + 174 района по стране (пожары, зима)</div>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0 h-full">
                <div class="kpi-label">Паводки — высокий риск</div>
                <div class="kpi-value">{{ loading ? '…' : highRisk.length }} НП</div>
                <div class="kpi-sub">скор ≥ 60 за текущий сезон</div>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0 h-full">
                <div class="kpi-label">Население в зоне риска</div>
                <div class="kpi-value">{{ loading ? '…' : populationAtRisk.toLocaleString('ru-RU') }}</div>
                <div class="kpi-sub">человек живёт в НП со скором ≥ 60</div>
            </div>
        </div>
        <div class="col-span-12 md:col-span-6 xl:col-span-3">
            <div class="card mb-0 h-full">
                <div class="kpi-label">Мер ждёт решения</div>
                <div class="kpi-value">{{ loading ? '…' : measureCounts.Proposed }}</div>
                <div class="kpi-sub">все контуры · утверждено: {{ measureCounts.Approved }}, выполнено: {{ measureCounts.Done }}</div>
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
                    <div>
                        <div class="stat-value" :class="{ 'stat-value--empty': fireCritical === null }">{{ fireCritical ?? '—' }}</div>
                        <div class="stat-sub">из них критических (ML ≥ 80)</div>
                    </div>
                </div>
                <template v-if="fireTop.length">
                    <div class="top-caption">Топ районов по ML-прогнозу{{ fireMl ? ` (от ${fireMl.generatedAt.slice(11, 16)} UTC)` : '' }}:</div>
                    <ul class="list-none p-0 m-0 flex flex-col">
                        <li v-for="d in fireTop" :key="d.id" class="top-row top-row--link" title="Открыть район на карте пожаров" @click="openDistrict('fire', d.id)">
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
                <div class="flex gap-9 mb-4 flex-wrap">
                    <div>
                        <div class="stat-value" :class="{ 'stat-value--empty': !winterLatest }">{{ winterLatest ? winterHigh : '—' }}</div>
                        <div class="stat-sub">районов с индексом ≥ 35</div>
                    </div>
                    <div>
                        <div class="stat-value" :class="{ 'stat-value--empty': !winterLatest }">{{ winterLatest ? winterSevere : '—' }}</div>
                        <div class="stat-sub">районов с индексом ≥ 60</div>
                    </div>
                    <div>
                        <div class="stat-value" :class="{ 'stat-value--empty': winterMlHigh === null }">{{ winterMlHigh ?? '—' }}</div>
                        <div class="stat-sub">районов с P(опасного дня) ≥ 10% — ML</div>
                    </div>
                </div>
                <template v-if="winterTop.length">
                    <div class="top-caption">Топ районов по индексу зимней опасности:</div>
                    <ul class="list-none p-0 m-0 flex flex-col">
                        <li v-for="d in winterTop" :key="d.id" class="top-row top-row--link" title="Открыть район на карте зимних рисков" @click="openDistrict('winter', d.id)">
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
                <div class="dash-card-title">Топ-10 НП по риску затопления <span class="text-muted-color text-sm font-normal">(клик — открыть на карте)</span></div>
                <DataTable :value="top10" size="small" :loading="loading" rowHover class="top10-table" @row-click="openSettlement($event.data)">
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
                <div class="dash-card-title">Очередь превентивных мер — все контуры</div>

                <!-- Разбивка по контурам: чип — ссылка на вкладку угрозы -->
                <div v-if="hasModuleInfo" class="queue-modules">
                    <RouterLink v-for="(hazard, module) in MODULE_HAZARD" :key="module" :to="`/risks/${hazard}`" class="queue-module-chip" :style="{ background: RISK_HAZARDS[hazard].bgColor }">
                        <HazardIcon :hazard="hazard" :size="14" />
                        {{ RISK_HAZARDS[hazard].label }}: {{ measuresByModule[module] ?? 0 }}
                    </RouterLink>
                </div>

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

                <!-- Ждут решения: топ по приоритету со всех контуров -->
                <template v-if="pendingTop.length">
                    <div class="top-caption" title="Шкалы приоритета у контуров разные: паводки — скор × lg(население), до ~550; районы — скор ≤ 100. Для общего топа приоритет нормирован к максимуму своего контура.">Ждут решения (топ по приоритету, нормирован внутри контура):</div>
                    <ul class="list-none p-0 m-0 flex flex-col mb-4">
                        <li v-for="m in pendingTop" :key="m.id" class="measure-row" :title="m.title" @click="$router.push(`/risks/${MODULE_HAZARD[m.module] ?? 'flood'}`)">
                            <span v-if="MODULE_HAZARD[m.module]" class="measure-row__chip" :style="{ background: RISK_HAZARDS[MODULE_HAZARD[m.module]].bgColor }">
                                <HazardIcon :hazard="MODULE_HAZARD[m.module]" :size="14" />
                            </span>
                            <span class="measure-row__body">
                                <span class="measure-row__name">{{ measureName(m) || RISK_HAZARDS[MODULE_HAZARD[m.module]]?.label }}</span>
                                <span class="measure-row__title">{{ m.title }}</span>
                            </span>
                            <span class="measure-row__aside">приоритет {{ Math.round(m.priority) }}</span>
                        </li>
                    </ul>
                </template>

                <!-- Последние решения комиссии -->
                <template v-if="recentDecisions.length">
                    <div class="top-caption">Последние решения комиссии:</div>
                    <ul class="list-none p-0 m-0 flex flex-col mb-4">
                        <li v-for="m in recentDecisions" :key="m.id" class="measure-row measure-row--static" :title="m.title">
                            <span v-if="MODULE_HAZARD[m.module]" class="measure-row__chip" :style="{ background: RISK_HAZARDS[MODULE_HAZARD[m.module]].bgColor }">
                                <HazardIcon :hazard="MODULE_HAZARD[m.module]" :size="14" />
                            </span>
                            <span class="measure-row__body">
                                <span class="measure-row__name">{{ measureName(m) || RISK_HAZARDS[MODULE_HAZARD[m.module]]?.label }}</span>
                                <span class="measure-row__title">{{ m.title }}<template v-if="m.decidedByName"> · {{ m.decidedByName }}</template></span>
                            </span>
                            <span class="measure-row__aside">
                                <Tag :value="MEASURE_STATUS[m.status]?.label ?? m.status" :severity="MEASURE_STATUS[m.status]?.severity ?? 'secondary'" />
                            </span>
                        </li>
                    </ul>
                </template>
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
.top-row--link {
    cursor: pointer;
}
.top-row--link:hover {
    background: var(--surface-hover);
}
.top10-table :deep(.p-datatable-tbody > tr) {
    cursor: pointer;
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
.queue-modules {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 14px;
}
.queue-module-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color);
}
/* Ряды мер (ждут решения / последние решения): чип контура + имя и мера в две строки */
.measure-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 6px;
    border-top: 1px solid var(--surface-border);
    cursor: pointer;
    border-radius: 6px;
}
.measure-row:hover {
    background: var(--surface-hover);
}
.measure-row--static {
    cursor: default;
}
.measure-row--static:hover {
    background: transparent;
}
.measure-row__chip {
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.measure-row__body {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
    flex: 1;
}
.measure-row__name {
    font-size: 14px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.measure-row__title {
    font-size: 12px;
    color: #98a2b3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.measure-row__aside {
    flex-shrink: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color-secondary);
}
.factor-cell {
    font-size: 13px;
    color: #0d9488;
}
</style>
