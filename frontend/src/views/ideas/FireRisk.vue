<script setup>
import KazakhstanMap from '@/components/KazakhstanMap.vue';
import { ref } from 'vue';

// Демо-скоры пожарного риска (0–100) — заменить на реальные данные NASA FIRMS + ERA5
// из API (module = 'fire-risk').
const demoScores = ref({
    'KZ-VOS': 84,
    'KZ-PAV': 76,
    'KZ-KAR': 71,
    'KZ-AKM': 58,
    'KZ-KUS': 52,
    'KZ-ALM': 47,
    'KZ-ZHA': 41,
    'KZ-SEV': 35,
    'KZ-AKT': 28,
    'KZ-ZAP': 24,
    'KZ-KZY': 19,
    'KZ-YUZ': 16,
    'KZ-ATY': 9,
    'KZ-MAN': 4
});

const selected = ref(null);
</script>

<template>
    <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12">
            <div class="card mb-0">
                <div class="flex items-center justify-between mb-4">
                    <div>
                        <h4 class="m-0">И-9. Степные/лесные пожары</h4>
                        <span class="text-muted-color">Риск-карта и раннее оповещение. Данные: NASA FIRMS (очаги), ERA5 (метео).</span>
                    </div>
                    <Tag value="демо-данные" severity="warn" />
                </div>
            </div>
        </div>

        <div class="col-span-12 lg:col-span-8">
            <div class="card mb-0">
                <KazakhstanMap :values="demoScores" legend-title="Риск пожара" @region-click="selected = $event" />
            </div>
        </div>

        <div class="col-span-12 lg:col-span-4">
            <div class="card mb-0 h-full">
                <h5>Регион</h5>
                <template v-if="selected">
                    <div class="text-2xl font-medium mb-2">{{ selected.name }}</div>
                    <div class="mb-4">
                        Скор риска: <Tag :value="selected.value ?? '—'" :severity="selected.value > 60 ? 'danger' : selected.value > 30 ? 'warn' : 'success'" />
                    </div>
                    <h6>Очередь патрулей (заглушка)</h6>
                    <ul class="list-disc pl-6 leading-loose">
                        <li>Патрулирование участков с сухостоем</li>
                        <li>Проверка минерализованных полос</li>
                        <li>Оповещение сельских акиматов</li>
                    </ul>
                </template>
                <p v-else class="text-muted-color">Кликните регион на карте, чтобы увидеть детали и очередь патрулей.</p>
            </div>
        </div>
    </div>
</template>
