<script setup>
import HazardTabs from '@/components/risk/HazardTabs.vue';
import { RISK_MODE_KEY } from '@/config/riskHazards';
import { computed, inject } from 'vue';

/**
 * Шапка модуля риска — верхняя карточка страницы «Риски», как в макете:
 * табы контуров, заголовок, описание и панель управления (сезон, live-погода,
 * детализация, кнопки).
 *
 * Состоянием вкладки владеет RisksCenter (provide/inject) — шапка лишь
 * рендерит табы, поэтому табы и заголовок остаются одной карточкой без
 * Teleport-хаков. Вне страницы «Риски» (нет provide) табы просто не рендерятся.
 */
defineProps({
    title: { type: String, required: true },
    description: { type: String, default: '' }
});

const injectedMode = inject(RISK_MODE_KEY, null);
const mode = computed({
    get: () => injectedMode?.value ?? null,
    set: (value) => {
        if (injectedMode) injectedMode.value = value;
    }
});
</script>

<template>
    <div class="card mb-0 risk-header-card">
        <div v-if="mode" class="risk-header-card__tabs">
            <HazardTabs v-model="mode" />
        </div>
        <div class="risk-header-card__body">
            <div class="risk-header-card__title">{{ title }}</div>
            <div v-if="description" class="risk-header-card__description">{{ description }}</div>
            <div class="risk-header-card__controls">
                <slot name="controls" />
            </div>
            <slot name="messages" />
        </div>
    </div>
</template>

<style scoped>
.risk-header-card {
    padding: 0;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
}
.risk-header-card__tabs {
    padding: 1.25rem 1.75rem 0;
    border-bottom: 1px solid var(--surface-border);
}
.risk-header-card__body {
    padding: 1.25rem 1.75rem 1.5rem;
}
.risk-header-card__title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 6px;
}
.risk-header-card__description {
    font-size: 14px;
    color: var(--text-color-secondary);
    margin-bottom: 20px;
}
.risk-header-card__controls {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
}
</style>
