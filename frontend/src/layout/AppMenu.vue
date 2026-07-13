<script setup>
import { ref } from 'vue';
import AppMenuItem from './AppMenuItem.vue';

const model = ref([
    {
        label: 'Главная',
        items: [
            {
                label: 'Дашборд',
                icon: 'pi pi-fw pi-home',
                to: '/'
            }
        ]
    },
    {
        label: 'Идеи',
        items: [
            {
                label: 'И-6. Паводковый риск',
                icon: 'pi pi-fw pi-cloud',
                to: '/ideas/flood-risk'
            },
            {
                label: 'И-9. Пожарный риск',
                icon: 'pi pi-fw pi-sun',
                to: '/ideas/fire-risk'
            },
            {
                label: 'Браконьерство',
                icon: 'pi pi-fw pi-eye',
                to: '/ideas/poaching'
            }
        ]
    },
    {
        label: 'Аккаунт',
        items: [
            {
                label: 'Настройки',
                icon: 'pi pi-fw pi-cog',
                to: '/account/settings'
            }
        ]
    }
]);
</script>

<template>
    <ul class="layout-menu">
        <template v-for="(item, i) in model" :key="item">
            <app-menu-item v-if="!item.separator" :item="item" :index="i"></app-menu-item>
            <li v-if="item.separator" class="menu-separator"></li>
        </template>
    </ul>
</template>

<style lang="scss" scoped></style>
