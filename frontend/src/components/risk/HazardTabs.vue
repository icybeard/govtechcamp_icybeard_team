<script setup>
import HazardIcon from '@/components/risk/HazardIcon.vue';
import { RISK_HAZARD_LIST } from '@/config/riskHazards';

/**
 * Переключатель контуров природных рисков (паводки/пожары/зима): иконка +
 * подчёркивание цветом контура у активной вкладки. Живёт в шапке активного
 * модуля (RiskHeaderCard) — вместе они образуют единую карточку страницы «Риски».
 */
defineProps({
    modelValue: { type: String, required: true }
});
defineEmits(['update:modelValue']);
</script>

<template>
    <div class="hazard-tabs">
        <div
            v-for="hazard in RISK_HAZARD_LIST"
            :key="hazard.value"
            class="hazard-tab"
            :style="{ borderBottomColor: modelValue === hazard.value ? hazard.color : 'transparent' }"
            @click="$emit('update:modelValue', hazard.value)"
        >
            <HazardIcon :hazard="hazard.value" :color="modelValue === hazard.value ? hazard.color : '#9aa1ad'" />
            <span class="hazard-tab-label" :class="{ active: modelValue === hazard.value }">{{ hazard.label }}</span>
        </div>
    </div>
</template>

<style scoped>
.hazard-tabs {
    display: flex;
    gap: 28px;
}
.hazard-tab {
    display: flex;
    align-items: center;
    gap: 9px;
    padding-bottom: 18px;
    margin-bottom: -1px;
    border-bottom: 2px solid transparent;
    cursor: pointer;
}
.hazard-tab-label {
    font-size: 16px;
    font-weight: 400;
    color: var(--text-color-secondary);
    letter-spacing: -0.01em;
}
.hazard-tab-label.active {
    font-weight: 600;
    color: var(--text-color);
}
</style>
