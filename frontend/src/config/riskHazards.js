/**
 * Единый реестр контуров природных рисков.
 *
 * Источник правды для цвета/подписи/иконки каждого контура — используется
 * переключателем табов (HazardTabs) наверху страницы «Риски» и самими
 * модулями (акцентный цвет графика, полоска карточки объекта на карте).
 *
 * Порядок следования — порядок вкладок в UI: паводки → пожары → зима.
 */

export const RISK_HAZARDS = Object.freeze({
    flood: {
        value: 'flood',
        label: 'Паводки',
        color: '#0ea5e9',
        bgColor: '#e0f2fe', // светлая подложка чипов/плашек контура (дашборд)
        icon: 'M12 5.5C9 9.5 6.5 12.3 6.5 15a5.5 5.5 0 0 0 11 0c0-2.7-2.5-5.5-5.5-9.5z'
    },
    fire: {
        value: 'fire',
        label: 'Пожары',
        color: '#f97316',
        bgColor: '#fff1e6',
        icon: 'M12 21a6 6 0 0 0 6-6c0-2.5-1.5-4-2.7-5.3.1 2-.9 3-1.8 2.3 1-3-1-5.3-3.7-7.5C10.3 7.5 8 9 8 12c0 1 .3 1.8.8 2.5C8.3 15.2 8 16 8 17a6 6 0 0 0 4 4z'
    },
    // 'snowflake' — не svg-path, а маркер для отдельного рендера иконки в HazardIcon
    winter: {
        value: 'winter',
        label: 'Зима',
        color: '#6366f1',
        bgColor: '#eef2ff',
        icon: 'snowflake'
    }
});

export const RISK_HAZARD_LIST = Object.values(RISK_HAZARDS);

/**
 * Ключ provide/inject для активного контура: состояние вкладки живёт в
 * RisksCenter, а сами табы рендерит шапка модуля (RiskHeaderCard) — так табы
 * и заголовок остаются одной карточкой, как в макете, без Teleport-хаков.
 */
export const RISK_MODE_KEY = Symbol('risk-mode');
