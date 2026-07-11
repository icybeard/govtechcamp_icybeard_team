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
    },
    {
        label: 'Справочник (Sakai UI Kit)',
        items: [
            {
                label: 'Form Layout',
                icon: 'pi pi-fw pi-id-card',
                to: '/uikit/formlayout'
            },
            {
                label: 'Input',
                icon: 'pi pi-fw pi-check-square',
                to: '/uikit/input'
            },
            {
                label: 'Button',
                icon: 'pi pi-fw pi-mobile',
                to: '/uikit/button'
            },
            {
                label: 'Table',
                icon: 'pi pi-fw pi-table',
                to: '/uikit/table'
            },
            {
                label: 'List',
                icon: 'pi pi-fw pi-list',
                to: '/uikit/list'
            },
            {
                label: 'Tree',
                icon: 'pi pi-fw pi-share-alt',
                to: '/uikit/tree'
            },
            {
                label: 'Panel',
                icon: 'pi pi-fw pi-tablet',
                to: '/uikit/panel'
            },
            {
                label: 'Overlay',
                icon: 'pi pi-fw pi-clone',
                to: '/uikit/overlay'
            },
            {
                label: 'Chart',
                icon: 'pi pi-fw pi-chart-bar',
                to: '/uikit/charts'
            },
            {
                label: 'CRUD',
                icon: 'pi pi-fw pi-pencil',
                to: '/pages/crud'
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
