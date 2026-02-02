import clsx from 'clsx';

export const Card = ({
  title,
  children,
  action,
  className = '',
  padding = true,
}) => {
  return (
    <div className={clsx('bg-white rounded-lg shadow-md', className)}>
      {title && (
        <div className={clsx('flex items-center justify-between border-b border-gray-200', padding ? 'p-6 pb-4' : 'p-4')}>
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          {action && <div>{action}</div>}
        </div>
      )}
      <div className={clsx(padding && 'p-6', title && 'pt-4')}>
        {children}
      </div>
    </div>
  );
};

export default Card;
