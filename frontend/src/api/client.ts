import axios from 'axios';
import type {
  ComplianceDashboard,
  DocumentResponse,
  ExtractionResult,
  GoldRecord,
  InconsistencyAlert,
  SupplierSummary,
  TokenResponse,
  User,
} from '../types';

const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL as string) || (import.meta.env.PROD ? '' : 'http://localhost:8000'),
  headers: { 'Content-Type': 'application/json' },
});

// Inject JWT token on every request if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ─── Auth ─────────────────────────────────────────────────────────────────────

export async function register(email: string, password: string, full_name: string, role: 'user' | 'admin' = 'user'): Promise<User> {
  const res = await api.post<User>('/api/auth/register', { email, password, full_name, role });
  return res.data;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  const res = await api.post<TokenResponse>('/api/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return res.data;
}

export async function getMe(): Promise<User> {
  const res = await api.get<User>('/api/auth/me');
  return res.data;
}

// ─── Documents ───────────────────────────────────────────────────────────────

export async function uploadDocuments(files: File[]): Promise<DocumentResponse[]> {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  const res = await api.post<DocumentResponse[]>('/api/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function listDocuments(): Promise<DocumentResponse[]> {
  const res = await api.get<DocumentResponse[]>('/api/documents/');
  return res.data;
}

export async function getDocument(id: string): Promise<DocumentResponse> {
  const res = await api.get<DocumentResponse>(`/api/documents/${id}`);
  return res.data;
}

export async function getExtraction(id: string): Promise<ExtractionResult> {
  const res = await api.get<ExtractionResult>(`/api/documents/${id}/extraction`);
  return res.data;
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/api/documents/${id}`);
}

// ─── Alertes ─────────────────────────────────────────────────────────────────

export async function listAlerts(): Promise<InconsistencyAlert[]> {
  const res = await api.get<InconsistencyAlert[]>('/api/alerts/');
  return res.data;
}

// ─── Métier ──────────────────────────────────────────────────────────────────

export async function getCrmSuppliers(): Promise<SupplierSummary[]> {
  const res = await api.get<SupplierSummary[]>('/api/crm/suppliers');
  return res.data;
}

export async function getSupplierDocuments(siren: string): Promise<GoldRecord[]> {
  const res = await api.get<GoldRecord[]>(`/api/crm/suppliers/${siren}`);
  return res.data;
}

export async function getComplianceDashboard(): Promise<ComplianceDashboard> {
  const res = await api.get<ComplianceDashboard>('/api/compliance/dashboard');
  return res.data;
}
