import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { message, Modal } from 'antd';

const BASE_URL = 'http://127.0.0.1:5555/api/v1';

export const pendingRequests = new Map<string, AbortController>();

export const cancelAllRequests = () => {
  pendingRequests.forEach((controller) => controller.abort());
  pendingRequests.clear();
};

export function generateRequestKey(config: InternalAxiosRequestConfig): string {
  const { method, url, params, data } = config;
  return `${method}:${url}:${JSON.stringify(params)}:${JSON.stringify(data)}`;
}

export function removePendingRequest(key: string) {
  const controller = pendingRequests.get(key);
  if (controller) {
    controller.abort();
    pendingRequests.delete(key);
  }
}

let retryCount = 0;
const MAX_RETRY_COUNT = 3;
const RETRY_DELAY = 1000;

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

client.interceptors.request.use(
  (config) => {
    const requestKey = generateRequestKey(config);
    
    removePendingRequest(requestKey);
    
    const controller = new AbortController();
    config.signal = controller.signal;
    pendingRequests.set(requestKey, controller);
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

client.interceptors.response.use(
  (response: AxiosResponse) => {
    const requestKey = generateRequestKey(response.config);
    removePendingRequest(requestKey);
    
    const data = response.data;
    
    if (data && typeof data === 'object' && 'success' in data && data.success === false) {
      const errorMsg = data.message || data.error || '请求失败';
      message.error(errorMsg);
    }
    
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    
    if (axios.isCancel(error)) {
      return Promise.reject(error);
    }
    
    const requestKey = generateRequestKey(error.config);
    removePendingRequest(requestKey);
    
    if (originalRequest && !originalRequest._retry && error.code === 'ECONNABORTED') {
      originalRequest._retry = true;
      
      if (retryCount < MAX_RETRY_COUNT) {
        retryCount++;
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY * retryCount));
        
        try {
          const response = await client(originalRequest);
          retryCount = 0;
          return response;
        } catch (retryError) {
          retryCount = 0;
          throw retryError;
        }
      }
      retryCount = 0;
    }
    
    const status = error.response?.status;
    const data = error.response?.data;
    const errorMsg = data?.message || data?.error || error.message;

    switch (status) {
      case 400:
        message.error(errorMsg || '请求参数错误');
        Modal.error({ title: '请求错误', content: errorMsg || '请求参数错误' });
        break;
      case 401:
        message.warning('未授权');
        Modal.warning({ title: '权限错误', content: '未授权，请重新登录' });
        break;
      case 403:
        message.warning(errorMsg || '权限不足');
        Modal.warning({ title: '权限不足', content: errorMsg || '权限不足' });
        break;
      case 404:
        message.warning(errorMsg || '资源不存在');
        break;
      case 500:
        message.error(errorMsg || '服务器内部错误');
        Modal.error({ title: '服务器错误', content: errorMsg || '服务器内部错误' });
        break;
      case 502:
      case 503:
      case 504:
        message.error('后端服务暂不可用');
        Modal.error({ title: '服务不可用', content: '后端服务暂不可用，请检查后端服务' });
        break;
      default:
        if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
          message.warning('请求超时');
          Modal.warning({ title: '请求超时', content: '请求超时，请检查网络' });
        } else if (error.code === 'ERR_NETWORK') {
          message.error('网络连接失败');
          Modal.error({ title: '网络错误', content: '网络连接失败，请检查后端服务' });
        } else {
          message.error(errorMsg || '请求失败');
        }
    }

    return Promise.reject(error);
  }
);

export default client;