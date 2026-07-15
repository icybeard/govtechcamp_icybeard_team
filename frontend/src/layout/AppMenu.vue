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
                label: 'Паводковый риск · СКО',
                icon: 'pi pi-fw pi-cloud',
                to: '/risks/flood'
            },
            {
                label: 'Пожарная обстановка · live',
                icon: 'pi pi-fw pi-sun',
                to: '/risks/fire'
            },
            {
                label: 'Зимняя обстановка',
                icon: 'pi pi-fw pi-asterisk',
                to: '/risks/winter'
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
