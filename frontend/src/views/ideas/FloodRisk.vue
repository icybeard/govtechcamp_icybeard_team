<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { api } from '@/service/api';
import { onMounted, ref } from 'vue';

const REGION = 'KZ-SEV'; // СКО — пилотный регион И-6 (см. docs/ideas/i6-flood-risk/plan.md)
const MODULE = 'flood-risk';

const loading = ref(true);
const error = ref(null);
const points = ref([]);
const regionValues = ref({});
const selected = ref(null);

onMounted(async () => {
    try {
        // Скоры НП (точки на карте) и областной хороплет — из БД, куда пишет ML-пайплайн
        const [settlementScores, regionScores] = await Promise.all([
            api.get(`/settlements/metrics/${MODULE}?metricKey=risk_score`),
            api.get(`/regions/metrics/${MODULE}?metricKey=risk_score`)
        ]);
        points.value = settlementScores.map((s) => ({
            id: s.settlementId,
            name: s.name,
            lat: s.lat,
            lon: s.lon,
            value: Math.round(s.value),
            population: s.population,
            factors: s.factors
        }));
        regionValues.value = regionScores;
    } catch (e) {
        error.value = e.message;
    } finally {
        loading.value = false;
    }
});
</script>

<template>
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h4 class="m-0">И-6. Паводковый риск-скоринг</h4>
                        <span class="text-muted-color">Риск весеннего затопления населённых пунктов. Пилот: Северо-Казахстанская область.</span>
                    </div>
                    <Tag v-if="points.length" :value="`НП со скорами: ${points.length}`" severity="success" />
                    <Tag v-else value="данные не загружены" severity="warn" />
                </div>
                <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
                <Message v-else-if="!loading && points.length === 0" severity="info" :closable="false">
                    Скоры ещё не загружены. Пайплайн: <code>scripts/download_settlements.py</code> → <code>scripts/load_settlements.py</code> → ML (<code>ml/i6-flood-risk/</code>) → <code>PUT /api/settlements/metrics</code>.
                </Message>
            </div>
        </div>

        <div class="col-span-12 lg:col-span-8">
            <div class="card mb-0">
                <KazakhstanMap :values="regionValues" :points="points" legend-title="Риск паводка" @point-click="selected = $event" @region-click="selected = null" />
            </div>
        </div>

        <div class="col-span-12 lg:col-span-4">
            <div class="card mb-0 h-full">
                <h5>Населённый пункт</h5>
                <template v-if="selected">
                    <div class="text-2xl font-medium mb-1">{{ selected.name }}</div>
                    <div class="text-muted-color mb-3" v-if="selected.population">Население: {{ selected.population.toLocaleString('ru-RU') }}</div>
                    <div class="mb-4">
                        Скор риска:
                        <Tag :value="selected.value ?? '—'" :severity="selected.value > 60 ? 'danger' : selected.value > 30 ? 'warn' : 'success'" />
                    </div>

                    <h6>Почему такой скор</h6>
                    <ul v-if="selected.factors?.length" class="list-none p-0 m-0 flex flex-col gap-2">
                        <li v-for="f in selected.factors" :key="f.name" class="flex items-center justify-between gap-3">
                            <span>{{ f.name }}</span>
                            <Tag :value="(f.impact > 0 ? '+' : '') + f.impact.toFixed(2)" :severity="f.impact > 0 ? 'danger' : 'success'" />
                        </li>
                    </ul>
                    <p v-else class="text-muted-color">Факторы появятся после загрузки SHAP-объяснений из ML-пайплайна.</p>
                </template>
                <p v-else class="text-muted-color">Кликните населённый пункт на карте — здесь появятся скор, объяснение факторов и очередь превентивных мер.</p>
            </div>
        </div>
    </div>
</template>
