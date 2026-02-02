import clsx from 'clsx';

export const Spinner = ({ size = 'md', className = '' }) => {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  };

  return (
    <div className={clsx('flex items-center justify-center', className)}>
      <div
        className={clsx(
          'animate-spin rounded-full border-b-2 border-indigo-600',
          sizeClasses[size]
        )}
      />
    </div>
  );
};

export default Spinner;
