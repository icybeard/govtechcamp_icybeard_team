<script setup>
import { RISK_MODE_KEY } from '@/config/riskHazards';
import { computed, provide, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import FireRisk from './ideas/FireRisk.vue';
import FloodRisk from './ideas/FloodRisk.vue';
import WinterRisk from './ideas/WinterRisk.vue';

// Единая страница природных рисков: табы переключают полные представления
// контуров (карта + панели + таблицы). KeepAlive сохраняет состояние и данные
// каждого контура между переключениями.
//
// Табы рендерит шапка активного модуля (RiskHeaderCard) — вместе с заголовком
// они образуют одну карточку, как в макете. Состояние вкладки живёт здесь
// и отдаётся шапке через provide(RISK_MODE_KEY).
const COMPONENTS = { flood: FloodRisk, fire: FireRisk, winter: WinterRisk };

const route = useRoute();
const router = useRouter();

const mode = ref(route.query.mode in COMPONENTS ? route.query.mode : 'flood');
watch(mode, (value) => router.replace({ query: { ...route.query, mode: value } }));
provide(RISK_MODE_KEY, mode);

const current = computed(() => COMPONENTS[mode.value]);
</script>

<template>
    <KeepAlive>
        <component :is="current" :key="mode" />
    </KeepAlive>
</template>
