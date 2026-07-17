<script setup>
import RiskScoreBadge from '@/components/risk/RiskScoreBadge.vue';
import { MEASURE_STATUS } from '@/config/measureStatus';
import { ruDistrictName } from '@/utils/districtNames';
import { computed, ref } from 'vue';

/**
 * Очередь превентивных мер — по макету: заголовок, пояснение приоритета,
 * таблица «объект / скор / мера / приоритет / статус / решение / действия».
 *
 * Общая для всех контуров: паводки передают меры и скоры НП, пожары и зима —
 * пока пустой список (макетное пустое состояние «загрузите скоры…»).
 * Решения (утвердить/отклонить/выполнено) уходят наружу событием set-status —
 * компонент не знает про API.
 */
const props = defineProps({
    measures: { type: Array, required: true },
    loading: { type: Boolean, default: false },
    entityLabel: { type: String, default: 'НП' }, // заголовок первой колонки: 'НП' | 'Район'
    scores: { type: Object, default: () => ({}) }, // settlementId -> скор 0–100
    canDecide: { type: Boolean, default: false }, // показывать ли кнопки решений комиссии
    priorityHint: { type: String, default: 'Приоритет = скор (0–100) × lg(население), шкала до ~550 — крупный НП выше в очереди; решение принимает комиссия' }
});
// explain — клик по строке или иконке «i»: страница открывает диалог
// «Почему рекомендовано» (объяснимость рекомендации)
defineEmits(['set-status', 'explain']);

// Фильтры аналитика: поиск по НП/району (ищет и по латинице, и по переводу),
// мера и статус — селекты с очисткой. Чисто отображение, данные не трогаем.
const search = ref('');
const titleFilter = ref(null);
const statusFilter = ref(null);

const titleOptions = computed(() => [...new Set(props.measures.map((m) => m.title))].sort().map((t) => ({ label: t, value: t })));
const statusOptions = Object.entries(MEASURE_STATUS).map(([value, s]) => ({ label: s.label, value }));

const filteredMeasures = computed(() =>
    props.measures.filter((m) => {
        if (titleFilter.value && m.title !== titleFilter.value) return false;
        if (statusFilter.value && m.status !== statusFilter.value) return false;
        if (search.value) {
            const query = search.value.toLowerCase();
            const name = m.settlementName || m.districtName || '';
            if (!name.toLowerCase().includes(query) && !ruDistrictName(name).toLowerCase().includes(query)) return false;
        }
        return true;
    })
);
</script>

<template>
    <div class="card mb-0">
        <div class="measures-head">
            <div class="measures-head__titles">
                <h5 class="m-0">Очередь превентивных мер</h5>
                <span class="text-muted-color measures-head__hint">{{ priorityHint }}</span>
            </div>
            <div class="measures-head__actions">
                <slot name="filter" />
            </div>
        </div>
        <div class="measures-filters">
            <IconField class="measures-filters__search">
                <InputIcon class="pi pi-search" />
                <InputText v-model="search" :placeholder="`Поиск: ${entityLabel}`" size="small" fluid />
            </IconField>
            <div class="measures-filters__right">
                <Select v-model="titleFilter" :options="titleOptions" optionLabel="label" optionValue="value" placeholder="Все меры" showClear size="small" style="min-width: 230px" />
                <Select v-model="statusFilter" :options="statusOptions" optionLabel="label" optionValue="value" placeholder="Все статусы" showClear size="small" style="min-width: 160px" />
                <Button v-if="search || titleFilter || statusFilter" v-tooltip.bottom="'Сбросить фильтры'" icon="pi pi-filter-slash" size="small" text severity="secondary" @click="((search = ''), (titleFilter = null), (statusFilter = null))" />
            </div>
        </div>
        <DataTable :value="filteredMeasures" paginator :rows="10" size="small" sortField="priority" :sortOrder="-1" :loading="loading" rowHover class="measures-table" @row-click="$emit('explain', $event.data)">
            <Column field="settlementName" :header="entityLabel" sortable>
                <!-- старые записи в БД — латиницей из geojson, переводим при отображении -->
                <template #body="{ data }">{{ ruDistrictName(data.settlementName || data.districtName || '—') }}</template>
            </Column>
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
/* Шапка очереди: заголовок и пояснение слева, действия (генерация, фильтр) — справа */
.measures-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 16px;
}
.measures-head__titles {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.measures-head__hint {
    font-size: 12px;
}
.measures-head__actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}
.measures-filters {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 14px;
    padding: 10px 12px;
    background: var(--surface-ground);
    border: 1px solid var(--surface-border);
    border-radius: 10px;
}
.measures-filters__search {
    width: 240px;
}
.measures-filters__right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

/* строка кликабельна — открывает «Почему рекомендовано» */
.measures-table :deep(.p-datatable-tbody > tr) {
    cursor: pointer;
}
</style>
