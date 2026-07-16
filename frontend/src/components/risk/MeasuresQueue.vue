<script setup>
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import { MEASURE_STATUS } from '@/config/measureStatus';

/**
 * Очередь превентивных мер — по макету: заголовок, пояснение приоритета,
 * таблица «объект / скор / мера / приоритет / статус / решение / действия».
 *
 * Общая для всех контуров: паводки передают меры и скоры НП, пожары и зима —
 * пока пустой список (макетное пустое состояние «загрузите скоры…»).
 * Решения (утвердить/отклонить/выполнено) уходят наружу событием set-status —
 * компонент не знает про API.
 */
defineProps({
    measures: { type: Array, required: true },
    loading: { type: Boolean, default: false },
    entityLabel: { type: String, default: 'НП' }, // заголовок первой колонки: 'НП' | 'Район'
    scores: { type: Object, default: () => ({}) }, // settlementId -> скор 0–100
    canDecide: { type: Boolean, default: false } // показывать ли кнопки решений комиссии
});
// explain — клик по строке или иконке «i»: страница открывает диалог
// «Почему рекомендовано» (объяснимость рекомендации)
defineEmits(['set-status', 'explain']);
</script>

<template>
    <div class="card mb-0">
        <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
            <div class="flex items-center gap-3">
                <h5 class="m-0">Очередь превентивных мер</h5>
                <slot name="filter" />
            </div>
            <span class="text-muted-color">Приоритет = скор риска × lg(население); решение принимает комиссия</span>
        </div>
        <DataTable :value="measures" paginator :rows="10" size="small" sortField="priority" :sortOrder="-1" :loading="loading" rowHover class="measures-table" @row-click="$emit('explain', $event.data)">
            <Column field="settlementName" :header="entityLabel" sortable />
            <Column header="Скор" style="width: 6rem">
                <template #body="{ data }">
                    <RiskScoreBadge :score="scores[data.settlementId]" />
                </template>
            </Column>
            <Column field="title" header="Мера" />
            <Column field="priority" header="Приоритет" sortable style="width: 8rem" />
            <Column field="status" header="Статус" sortable style="width: 10rem">
                <template #body="{ data }">
                    <Tag :value="MEASURE_STATUS[data.status]?.label ?? data.status" :severity="MEASURE_STATUS[data.status]?.severity ?? 'secondary'" />
                </template>
            </Column>
            <Column field="decidedByName" header="Решение принял" style="width: 12rem">
                <template #body="{ data }">
                    <span v-if="data.decidedByName">{{ data.decidedByName }}</span>
                    <span v-else class="text-muted-color">—</span>
                </template>
            </Column>
            <Column header="Действия" style="width: 14rem">
                <template #body="{ data }">
                    <div class="flex gap-2 items-center">
                        <Button v-tooltip.left="'Почему рекомендовано'" icon="pi pi-info-circle" size="small" text @click.stop="$emit('explain', data)" />
                        <template v-if="canDecide && data.status === 'Proposed'">
                            <Button label="Утвердить" size="small" severity="success" outlined @click.stop="$emit('set-status', data, 'Approved')" />
                            <Button icon="pi pi-times" size="small" severity="danger" outlined @click.stop="$emit('set-status', data, 'Rejected')" />
                        </template>
                        <Button v-else-if="canDecide && data.status === 'Approved'" label="Выполнено" size="small" severity="info" outlined @click.stop="$emit('set-status', data, 'Done')" />
                    </div>
                </template>
            </Column>
            <template #empty>
                <slot name="empty">Очередь пуста — загрузите скоры и сгенерируйте черновики мер.</slot>
            </template>
        </DataTable>
    </div>
</template>

<style scoped>
/* строка кликабельна — открывает «Почему рекомендовано» */
.measures-table :deep(.p-datatable-tbody > tr) {
    cursor: pointer;
}
</style>
