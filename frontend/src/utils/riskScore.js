/**
 * Единая шкала риска 0–100, общая для всех контуров (паводки/пожары/зима).
 *
 * Раньше пороги дублировались инлайн в каждом views/ideas/*.vue (где-то
 * 3 ступени, где-то своя функция sev()) — здесь один источник правды на
 * 4 ступени, из которого берут цвет и PrimeVue severity.
 */
const BUCKETS = [
    { max: 20, bg: '#ecfdf3', color: '#067647', severity: 'success' },
    { max: 40, bg: '#fef7e6', color: '#93720c', severity: 'warn' },
    { max: 60, bg: '#fef0e6', color: '#b93815', severity: 'warn' },
    { max: Infinity, bg: '#fee4e2', color: '#b42318', severity: 'danger' }
];

/** Возвращает { max, bg, color, severity } для скора 0–100, либо null для отсутствующего значения. */
export function riskBucket(score) {
    if (score === null || score === undefined || Number.isNaN(score)) return null;
    return BUCKETS.find((bucket) => score < bucket.max) ?? BUCKETS[BUCKETS.length - 1];
}

/** PrimeVue Tag severity ('success' | 'warn' | 'danger' | 'secondary') для скора. */
export function riskSeverity(score) {
    return riskBucket(score)?.severity ?? 'secondary';
}
