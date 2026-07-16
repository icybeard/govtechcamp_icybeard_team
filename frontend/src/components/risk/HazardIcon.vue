<script setup>
import { RISK_HAZARDS } from '@/config/riskHazards';
import { computed } from 'vue';

/**
 * Линейная иконка контура риска (капля/огонь/снежинка) — единый стиль по
 * дизайн-спецификации (stroke без заливки). Используется в табах контуров
 * и в чипах-плашках на дашборде; цвет по умолчанию — цвет контура,
 * переопределяется пропом (например, серый у неактивной вкладки).
 */
const props = defineProps({
    hazard: { type: String, required: true }, // ключ RISK_HAZARDS: 'flood' | 'fire' | 'winter'
    color: { type: String, default: null },
    size: { type: Number, default: 18 }
});

const config = computed(() => RISK_HAZARDS[props.hazard]);
const stroke = computed(() => props.color ?? config.value.color);

// Координаты точек снежинки — только для иконки зимы, остальные контуры используют svg-path из конфига
const SNOWFLAKE_DOTS = [
    { cx: 12, cy: 2.5 },
    { cx: 12, cy: 21.5 },
    { cx: 3.4, cy: 7.25 },
    { cx: 20.6, cy: 16.75 },
    { cx: 20.6, cy: 7.25 },
    { cx: 3.4, cy: 16.75 }
];
</script>

<template>
    <svg v-if="config.icon !== 'snowflake'" :width="size" :height="size" viewBox="0 0 24 24" fill="none">
        <path :d="config.icon" :stroke="stroke" stroke-width="2" stroke-linejoin="round" />
    </svg>
    <svg v-else :width="size" :height="size" viewBox="0 0 24 24" fill="none" :stroke="stroke" stroke-width="1.7" stroke-linecap="round">
        <path d="M12 2.5v19M3.4 7.25l17.2 9.5M20.6 7.25L3.4 16.75" />
        <circle v-for="dot in SNOWFLAKE_DOTS" :key="`${dot.cx}-${dot.cy}`" :cx="dot.cx" :cy="dot.cy" r="1" :fill="stroke" stroke="none" />
    </svg>
</template>
