import { format, formatDistanceToNow } from 'date-fns';

/**
 * Format a date to a readable string
 * @param {string|Date} date - Date to format
 * @returns {string} Formatted date string
 */
export const formatDate = (date) => {
  if (!date) return 'N/A';
  return format(new Date(date), 'MMM d, yyyy h:mm a');
};

/**
 * Format a date as relative time (e.g., "2 hours ago")
 * @param {string|Date} date - Date to format
 * @returns {string} Relative time string
 */
export const formatRelativeTime = (date) => {
  if (!date) return 'N/A';
  return formatDistanceToNow(new Date(date), { addSuffix: true });
};

/**
 * Truncate text to a maximum length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text
 */
export const truncateText = (text, maxLength = 100) => {
  if (!text || text.length <= maxLength) return text;
  return `${text.substring(0, maxLength)}...`;
};

/**
 * Format a score as percentage
 * @param {number} score - Score (0-1 or 0-100)
 * @returns {string} Formatted percentage
 */
export const formatScore = (score) => {
  if (typeof score !== 'number') return 'N/A';
  const percentage = score <= 1 ? score * 100 : score;
  return `${percentage.toFixed(1)}%`;
};

/**
 * Get score color class based on value
 * @param {number} score - Score (0-1 or 0-100)
 * @returns {string} Tailwind color class
 */
export const getScoreColor = (score) => {
  if (typeof score !== 'number') return 'text-gray-500';
  const value = score <= 1 ? score * 100 : score;
  if (value >= 80) return 'text-green-600';
  if (value >= 60) return 'text-yellow-600';
  return 'text-red-600';
};

/**
 * Format large numbers with commas
 * @param {number} num - Number to format
 * @returns {string} Formatted number
 */
export const formatNumber = (num) => {
  if (typeof num !== 'number') return '0';
  return num.toLocaleString();
};
