// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const APP_NAME = import.meta.env.VITE_APP_NAME || 'Evolving AI Agent';

// Navigation Routes
export const ROUTES = {
  HOME: '/',
  CHAT: '/chat',
  MEMORY: '/memory',
  KNOWLEDGE: '/knowledge',
  GITHUB: '/github',
  ANALYTICS: '/analytics',
  SETTINGS: '/settings',
};

// Knowledge Categories
export const KNOWLEDGE_CATEGORIES = [
  'General',
  'Technical',
  'Domain',
  'Behavioral',
  'User Preferences',
];

// Evaluation Criteria
export const EVALUATION_CRITERIA = [
  'accuracy',
  'completeness',
  'clarity',
  'relevance',
  'creativity',
  'efficiency',
  'safety',
];

// Colors for badges and status indicators
export const STATUS_COLORS = {
  success: 'bg-green-100 text-green-800',
  warning: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
  info: 'bg-blue-100 text-blue-800',
  neutral: 'bg-gray-100 text-gray-800',
};

export const BADGE_COLORS = {
  primary: 'bg-indigo-100 text-indigo-800',
  secondary: 'bg-gray-100 text-gray-800',
  success: 'bg-green-100 text-green-800',
  danger: 'bg-red-100 text-red-800',
  warning: 'bg-yellow-100 text-yellow-800',
  info: 'bg-blue-100 text-blue-800',
};
