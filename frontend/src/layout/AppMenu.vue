<script setup>
import { ref } from 'vue';
import AppMenuItem from './AppMenuItem.vue';

const model = ref([
    {
        label: 'Обзор',
        items: [
            {
                label: 'Дашборд',
                icon: 'pi pi-fw pi-home',
                to: '/'
            }
        ]
    },
    {
        label: 'Природные риски',
        items: [
            {
                label: 'Ситуационная карта',
                icon: 'pi pi-fw pi-map',
                to: '/risks'
            },
            {
                label: 'Данные',
                icon: 'pi pi-fw pi-database',
                to: '/data'
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
