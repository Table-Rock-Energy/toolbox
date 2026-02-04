import { Link } from 'react-router-dom'
import {
  FileSearch,
  FileText,
  Calculator,
  DollarSign,
  ArrowRight,
  Activity,
  Clock,
  CheckCircle,
} from 'lucide-react'
import { StatusBadge } from '../components'

const tools = [
  {
    name: 'Extract',
    description: 'Extract data from PDFs and documents using AI',
    icon: FileSearch,
    path: '/extract',
    color: 'bg-blue-500',
  },
  {
    name: 'Title',
    description: 'Manage and search mineral title information',
    icon: FileText,
    path: '/title',
    color: 'bg-green-500',
  },
  {
    name: 'Proration',
    description: 'Calculate interest prorations and allocations',
    icon: Calculator,
    path: '/proration',
    color: 'bg-purple-500',
  },
  {
    name: 'Revenue',
    description: 'Analyze revenue statements and distributions',
    icon: DollarSign,
    path: '/revenue',
    color: 'bg-amber-500',
  },
]

const recentActivity = [
  {
    id: 1,
    type: 'Extract',
    description: 'Processed lease document',
    status: 'success' as const,
    time: '2 hours ago',
  },
  {
    id: 2,
    type: 'Proration',
    description: 'Calculated interest allocation',
    status: 'success' as const,
    time: '5 hours ago',
  },
  {
    id: 3,
    type: 'Revenue',
    description: 'Processing statement upload',
    status: 'processing' as const,
    time: '1 day ago',
  },
  {
    id: 4,
    type: 'Title',
    description: 'Title search completed',
    status: 'success' as const,
    time: '2 days ago',
  },
]

export default function Dashboard() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-oswald font-semibold text-tre-navy">
          Dashboard
        </h1>
        <p className="text-gray-500 mt-1">
          Welcome to Table Rock Tools. Select a tool to get started.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-tre-teal/10 rounded-lg">
              <Activity className="w-5 h-5 text-tre-teal" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-tre-navy">127</p>
              <p className="text-sm text-gray-500">Total Jobs</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-tre-navy">118</p>
              <p className="text-sm text-gray-500">Completed</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <Clock className="w-5 h-5 text-yellow-600" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-tre-navy">9</p>
              <p className="text-sm text-gray-500">In Progress</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-tre-brown-light/20 rounded-lg">
              <FileText className="w-5 h-5 text-tre-brown-medium" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-tre-navy">1,240</p>
              <p className="text-sm text-gray-500">Documents</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tools Grid */}
      <div>
        <h2 className="text-xl font-oswald font-semibold text-tre-navy mb-4">
          Tools
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {tools.map((tool) => (
            <Link
              key={tool.path}
              to={tool.path}
              className="group bg-white rounded-xl border border-gray-200 p-5 hover:border-tre-teal hover:shadow-lg transition-all duration-200"
            >
              <div className={`w-12 h-12 ${tool.color} rounded-xl flex items-center justify-center mb-4`}>
                <tool.icon className="w-6 h-6 text-white" />
              </div>
              <h3 className="font-oswald font-semibold text-tre-navy text-lg mb-1 group-hover:text-tre-teal transition-colors">
                {tool.name}
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                {tool.description}
              </p>
              <div className="flex items-center text-tre-teal text-sm font-medium">
                Open Tool
                <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <h2 className="text-xl font-oswald font-semibold text-tre-navy mb-4">
          Recent Activity
        </h2>
        <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
          {recentActivity.map((item) => (
            <div key={item.id} className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-tre-navy/5 rounded-lg flex items-center justify-center">
                  <span className="text-xs font-medium text-tre-navy">{item.type.charAt(0)}</span>
                </div>
                <div>
                  <p className="font-medium text-gray-900">{item.description}</p>
                  <p className="text-sm text-gray-500">{item.type}</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <StatusBadge status={item.status} size="sm" />
                <span className="text-sm text-gray-400">{item.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
