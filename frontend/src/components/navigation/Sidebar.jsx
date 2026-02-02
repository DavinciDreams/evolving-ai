import { Link, useLocation } from 'react-router-dom';
import clsx from 'clsx';
import {
  HomeIcon,
  ChatBubbleLeftRightIcon,
  CircleStackIcon,
  BookOpenIcon,
  CodeBracketSquareIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline';
import { ROUTES } from '../../utils/constants';
import { useApp } from '../../context/AppContext';

const navigation = [
  { name: 'Home', href: ROUTES.HOME, icon: HomeIcon },
  { name: 'Chat', href: ROUTES.CHAT, icon: ChatBubbleLeftRightIcon },
  { name: 'Memory', href: ROUTES.MEMORY, icon: CircleStackIcon },
  { name: 'Knowledge', href: ROUTES.KNOWLEDGE, icon: BookOpenIcon },
  { name: 'GitHub', href: ROUTES.GITHUB, icon: CodeBracketSquareIcon },
  { name: 'Analytics', href: ROUTES.ANALYTICS, icon: ChartBarIcon },
];

export const Sidebar = () => {
  const location = useLocation();
  const { sidebarOpen } = useApp();

  if (!sidebarOpen) return null;

  return (
    <div className="flex flex-col w-64 bg-gray-900">
      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex items-center h-16 flex-shrink-0 px-4 bg-gray-800">
          <h1 className="text-xl font-bold text-white">Evolving AI</h1>
        </div>
        <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'group flex items-center px-3 py-2 text-sm font-medium rounded-md',
                  isActive
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                )}
              >
                <item.icon
                  className={clsx(
                    'mr-3 flex-shrink-0 h-6 w-6',
                    isActive ? 'text-white' : 'text-gray-400 group-hover:text-white'
                  )}
                />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
};

export default Sidebar;
