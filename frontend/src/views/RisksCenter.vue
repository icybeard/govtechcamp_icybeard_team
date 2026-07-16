<script setup>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import FireRisk from './ideas/FireRisk.vue';
import FloodRisk from './ideas/FloodRisk.vue';
import WinterRisk from './ideas/WinterRisk.vue';

// Единая страница природных рисков: слайдер переключает полные представления
// контуров (карта + панели + таблицы). KeepAlive сохраняет состояние и данные
// каждого контура между переключениями.
const MODES = [
    { label: '🌊 Паводки', value: 'flood', component: FloodRisk },
    { label: '🔥 Пожары', value: 'fire', component: FireRisk },
    { label: '❄️ Зима', value: 'winter', component: WinterRisk }
];

const route = useRoute();
const router = useRouter();

const mode = ref(MODES.some((m) => m.value === route.query.mode) ? route.query.mode : 'flood');
watch(mode, (value) => router.replace({ query: { ...route.query, mode: value } }));

const current = computed(() => MODES.find((m) => m.value === mode.value).component);
</script>

<template>
    <div class="flex flex-col gap-4">
        <div class="flex justify-center">
            <SelectButton v-model="mode" :options="MODES" optionLabel="label" optionValue="value" :allowEmpty="false" />
        </div>
        <KeepAlive>
            <component :is="current" :key="mode" />
        </KeepAlive>
    </div>
</template>
