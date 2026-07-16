/**
 * Статусы превентивных мер (backend: PreventiveMeasure.Status) — единый
 * словарь «код → подпись + severity PrimeVue» для очереди мер и карточек
 * объектов на карте.
 */
export const MEASURE_STATUS = Object.freeze({
    Proposed: { label: 'Предложено', severity: 'warn' },
    Approved: { label: 'Утверждено', severity: 'success' },
    Rejected: { label: 'Отклонено', severity: 'danger' },
    Done: { label: 'Выполнено', severity: 'info' }
});
