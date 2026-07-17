<script setup>
/**
 * Логотип платформы: щит (превенция/защита) с тремя волнами — слои сезонных
 * рисков в цветах контуров: зима (светло-голубой), паводки (синий),
 * пожары (оранжевый). Тот же знак — в public/favicon.svg (синхронизировать).
 */
defineProps({
    size: { type: Number, default: 32 }
});
</script>

<template>
    <svg :width="size" :height="size" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="IcyBeard">
        <defs>
            <linearGradient id="ib-shield" x1="24" y1="3" x2="24" y2="45" gradientUnits="userSpaceOnUse">
                <stop stop-color="#1E4266" />
                <stop offset="1" stop-color="#0F2A45" />
            </linearGradient>
            <clipPath id="ib-clip">
                <path d="M24 3L41 9.5V23C41 33.6 33.9 41.8 24 45C14.1 41.8 7 33.6 7 23V9.5L24 3Z" />
            </clipPath>
        </defs>
        <path d="M24 3L41 9.5V23C41 33.6 33.9 41.8 24 45C14.1 41.8 7 33.6 7 23V9.5L24 3Z" fill="url(#ib-shield)" />
        <g clip-path="url(#ib-clip)" stroke-linecap="round" fill="none">
            <path d="M4 15.5C9 12 14 12 19 15.5C24 19 29 19 34 15.5C39 12 44 12 49 15.5" stroke="#7DD3FC" stroke-width="3.4" />
            <path d="M4 24C9 20.5 14 20.5 19 24C24 27.5 29 27.5 34 24C39 20.5 44 20.5 49 24" stroke="#38BDF8" stroke-width="3.4" />
            <path d="M4 32.5C9 29 14 29 19 32.5C24 36 29 36 34 32.5C39 29 44 29 49 32.5" stroke="#FB923C" stroke-width="3.4" />
        </g>
        <path d="M24 3L41 9.5V23C41 33.6 33.9 41.8 24 45C14.1 41.8 7 33.6 7 23V9.5L24 3Z" stroke="#0B1F33" stroke-opacity="0.35" stroke-width="1.2" />
    </svg>
</template>
