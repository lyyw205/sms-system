import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Messages API
export const messagesAPI = {
  getAll: (params?: { skip?: number; limit?: number; direction?: string; phone?: string }) =>
    api.get('/api/messages', { params }),
  getContacts: () => api.get('/api/messages/contacts'),
  send: (data: { to: string; message: string }) =>
    api.post('/api/messages/send', data),
  getReviewQueue: () => api.get('/api/messages/review-queue'),
  simulateReceive: (data: { from_: string; to: string; message: string }) =>
    api.post('/webhooks/sms/receive', data),
};

// Reservations API
export const reservationsAPI = {
  getAll: (params?: { skip?: number; limit?: number; status?: string; date?: string }) =>
    api.get('/api/reservations', { params }),
  create: (data: any) => api.post('/api/reservations', data),
  update: (id: number, data: any) => api.put(`/api/reservations/${id}`, data),
  delete: (id: number) => api.delete(`/api/reservations/${id}`),
  assignRoom: (id: number, data: { room_number: string | null }) =>
    api.put(`/api/reservations/${id}/room`, data),
  syncNaver: () => api.post('/api/reservations/sync/naver'),
  syncSheets: () => api.post('/api/reservations/sync/sheets'),
};

// Rules API
export const rulesAPI = {
  getAll: () => api.get('/api/rules'),
  create: (data: any) => api.post('/api/rules', data),
  update: (id: number, data: any) => api.put(`/api/rules/${id}`, data),
  delete: (id: number) => api.delete(`/api/rules/${id}`),
};

// Documents API
export const documentsAPI = {
  getAll: () => api.get('/api/documents'),
  upload: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  delete: (id: number) => api.delete(`/api/documents/${id}`),
};

// Auto-response API
export const autoResponseAPI = {
  generate: (messageId: number) =>
    api.post('/api/auto-response/generate', { message_id: messageId }),
  test: (message: string) =>
    api.post('/api/auto-response/test', { message }),
  reloadRules: () => api.post('/api/auto-response/reload-rules'),
};

// Dashboard API
export const dashboardAPI = {
  getStats: () => api.get('/api/dashboard/stats'),
};

// Campaigns API
export const campaignsAPI = {
  getTargets: (tag: string, smsType: string = 'room', date?: string) =>
    api.get('/campaigns/targets', { params: { tag, sms_type: smsType, date } }),
  sendByTag: (data: { tag: string; template_key: string; variables?: any; sms_type?: string; date?: string }) =>
    api.post('/campaigns/send-by-tag', data),
  getHistory: (params?: { skip?: number; limit?: number }) =>
    api.get('/campaigns/history', { params }),
  getTemplates: () => api.get('/campaigns/templates'),
  sendRoomGuide: (data: { date?: string }) =>
    api.post('/campaigns/notifications/room-guide', data),
  sendPartyGuide: (data: { date?: string }) =>
    api.post('/campaigns/notifications/party-guide', data),
};

// Scheduler API
export const schedulerAPI = {
  getJobs: () => api.get('/scheduler/jobs'),
  runJob: (jobId: string) => api.post(`/scheduler/jobs/${jobId}/run`),
  pauseJob: (jobId: string) => api.post(`/scheduler/jobs/${jobId}/pause`),
  resumeJob: (jobId: string) => api.post(`/scheduler/jobs/${jobId}/resume`),
  getStatus: () => api.get('/scheduler/status'),
};

// Gender Stats API
export const genderStatsAPI = {
  get: (date?: string) => api.get('/campaigns/gender-stats', { params: { date } }),
  getHistory: (days?: number) =>
    api.get('/campaigns/gender-stats/history', { params: { days } }),
  refresh: (date?: string) => api.post('/campaigns/gender-stats/refresh', null, { params: { date } }),
};

export default api;
