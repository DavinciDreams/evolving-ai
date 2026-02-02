import { Bars3Icon } from '@heroicons/react/24/outline';
import { useApp } from '../../context/AppContext';
import Badge from '../common/Badge';

export const TopBar = () => {
  const { toggleSidebar } = useApp();

  return (
    <div className="sticky top-0 z-10 flex-shrink-0 flex h-16 bg-white shadow">
      <button
        type="button"
        className="px-4 border-r border-gray-200 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500"
        onClick={toggleSidebar}
      >
        <span className="sr-only">Toggle sidebar</span>
        <Bars3Icon className="h-6 w-6" aria-hidden="true" />
      </button>
      <div className="flex-1 px-4 flex justify-between">
        <div className="flex-1 flex items-center">
          <h2 className="text-xl font-semibold text-gray-900">
            AI Agent Dashboard
          </h2>
        </div>
        <div className="ml-4 flex items-center space-x-4">
          <Badge variant="success">Active</Badge>
        </div>
      </div>
    </div>
  );
};

export default TopBar;
