import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

// En un teléfono físico usa la IP local del servidor, nunca "localhost".
export const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://192.168.1.100:8000/api/v1';
const TOKEN_KEY = 'gestion_documental_access_token';


async function saveToken(token) {
  if (Platform.OS === 'web') {
    sessionStorage.setItem(TOKEN_KEY, token);
    return;
  }
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}


async function readToken() {
  if (Platform.OS === 'web') {
    return sessionStorage.getItem(TOKEN_KEY);
  }
  return SecureStore.getItemAsync(TOKEN_KEY);
}


export async function logout() {
  if (Platform.OS === 'web') {
    sessionStorage.removeItem(TOKEN_KEY);
    return;
  }
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}


async function request(path, options = {}) {
  const token = await readToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || `Error ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}


export async function login(email, password) {
  const result = await request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  await saveToken(result.access_token);
  return result;
}


export const getCurrentUser = () => request('/auth/me');
export const getTeams = () => request('/teams');
export const getDocuments = () => request('/documents');
export const createDocument = (data) => request('/documents', { method: 'POST', body: JSON.stringify(data) });
export const submitDocument = (documentId) => request(`/documents/${documentId}/submit`, { method: 'POST' });
export const reviewDocument = (documentId, decision, comment) => request(`/documents/${documentId}/review`, {
  method: 'POST', body: JSON.stringify({ decision, comment }),
});


export async function uploadDocumentVersion(documentId, asset) {
  const form = new FormData();
  // DocumentPicker entrega un File real en web; React Native usa uri/name/type.
  form.append('file', asset.file || { uri: asset.uri, name: asset.name, type: asset.mimeType || 'application/octet-stream' });
  return request(`/documents/${documentId}/versions`, { method: 'POST', body: form });
}
