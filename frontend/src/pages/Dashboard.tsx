import { Link } from 'react-router-dom'
import {
  FileSearch,
  FileText,
  Calculator,
  DollarSign,
  ArrowRight,
  Activity,
} from 'lucide-react'

const tools = [
  {
    name: 'Extract',
    description: 'Extract party and stakeholder data from OCC Exhibit A PDFs',
    icon: FileSearch,
    path: '/extract',
    color: 'bg-blue-500',
    usageCount: 0,
  },
  {
    name: 'Title',
    description: 'Consolidate owner and contact info from Oklahoma title opinions',
    icon: FileText,
    path: '/title',
    color: 'bg-green-500',
    usageCount: 0,
  },
  {
    name: 'Proration',
    description: 'Calculate interest prorations and NRA allocations with RRC data',
    icon: Calculator,
    path: '/proration',
    color: 'bg-purple-500',
    usageCount: 0,
  },
  {
    name: 'Revenue',
    description: 'Extract revenue statements from EnergyLink and Energy Transfer PDFs',
    icon: DollarSign,
    path: '/revenue',
    color: 'bg-amber-500',
    usageCount: 0,
  },
]

// This would come from the backend in a real implementation
const recentActivity: {
  id: number
  tool: string
  fileName: string
  user: string
  timestamp: string
}[] = []

export default function Dashboard() {
  const totalJobs = tools.reduce((sum, tool) => sum + tool.usageCount, 0)

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

      {/* Stats - Total Jobs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-tre-teal/10 rounded-lg">
              <Activity className="w-5 h-5 text-tre-teal" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-tre-navy">{totalJobs}</p>
              <p className="text-sm text-gray-500">Total Jobs</p>
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
              <div className="flex items-start justify-between mb-4">
                <div className={`w-12 h-12 ${tool.color} rounded-xl flex items-center justify-center`}>
                  <tool.icon className="w-6 h-6 text-white" />
                </div>
                <div className="text-right">
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">{tool.usageCount}</p>
                  <p className="text-xs text-gray-400">times used</p>
                </div>
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
        <div className="bg-white rounded-xl border border-gray-200">
          {recentActivity.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              <Activity className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p className="font-medium">No activity yet</p>
              <p className="text-sm mt-1">Tool usage will appear here</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Tool</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">File</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Date & Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentActivity.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-tre-teal/10 text-tre-teal">
                        {item.tool}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">{item.fileName}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{item.user}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{item.timestamp}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
