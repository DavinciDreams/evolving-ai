import clsx from 'clsx';
import { useId } from 'react';

export const Input = ({
  label,
  error,
  id,
  className = '',
  ...props
}) => {
  const generatedId = useId();
  const inputId = id || generatedId;
  const errorId = `${inputId}-error`;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-gray-700 mb-1">
          {label}
        </label>
      )}
      <input
        id={inputId}
        aria-describedby={error ? errorId : undefined}
        aria-invalid={error ? 'true' : undefined}
        className={clsx(
          'w-full px-3 py-2 border rounded-md shadow-sm',
          'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
          error ? 'border-red-300' : 'border-gray-300',
          className
        )}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-1 text-sm text-red-600">{error}</p>
      )}
    </div>
  );
};

export default Input;
