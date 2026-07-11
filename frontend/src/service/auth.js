import { computed, ref } from 'vue';
import { api, getToken, setToken } from './api';

const user = ref(null);
const initialized = ref(false);

export const currentUser = computed(() => user.value);
export const isAuthenticated = computed(() => user.value !== null);
export const isAdmin = computed(() => user.value?.role === 'Admin');

export async function initAuth() {
    if (initialized.value) return;
    initialized.value = true;
    if (!getToken()) return;
    try {
        user.value = await api.get('/auth/me');
    } catch {
        setToken(null);
    }
}

export async function login(email, password) {
    const result = await api.post('/auth/login', { email, password });
    setToken(result.token);
    user.value = result.user;
    return result.user;
}

export async function register(email, password, displayName) {
    const result = await api.post('/auth/register', { email, password, displayName });
    setToken(result.token);
    user.value = result.user;
    return result.user;
}

export function logout() {
    setToken(null);
    user.value = null;
}

export async function updateProfile(displayName) {
    user.value = await api.put('/account/profile', { displayName });
    return user.value;
}

export async function changePassword(currentPassword, newPassword) {
    await api.put('/account/password', { currentPassword, newPassword });
}
