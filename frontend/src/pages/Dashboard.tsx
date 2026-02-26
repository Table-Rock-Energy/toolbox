import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  FileSearch,
  FileText,
  Calculator,
  DollarSign,
  Repeat,
  ArrowRight,
  Activity,
  CheckCircle,
  XCircle,
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

interface ToolConfig {
  name: string
  tool: string
  description: string
  icon: typeof FileSearch
  path: string
  color: string
}

const toolConfigs: ToolConfig[] = [
  {
    name: 'Extract',
    tool: 'extract',
    description: 'Extract party and stakeholder data from OCC Exhibit A PDFs',
    icon: FileSearch,
    path: '/extract',
    color: 'bg-blue-500',
  },
  {
    name: 'Title',
    tool: 'title',
    description: 'Consolidate owner and contact info from Oklahoma title opinions',
    icon: FileText,
    path: '/title',
    color: 'bg-green-500',
  },
  {
    name: 'Proration',
    tool: 'proration',
    description: 'Calculate interest prorations and NRA allocations with RRC data',
    icon: Calculator,
    path: '/proration',
    color: 'bg-purple-500',
  },
  {
    name: 'Revenue',
    tool: 'revenue',
    description: 'Extract revenue statements from EnergyLink and Energy Transfer PDFs',
    icon: DollarSign,
    path: '/revenue',
    color: 'bg-amber-500',
  },
  {
    name: 'GHL Prep',
    tool: 'ghl_prep',
    description: 'Transform Mineral export CSVs for GoHighLevel import',
    icon: Repeat,
    path: '/ghl-prep',
    color: 'bg-orange-500',
  },
]

interface RecentJob {
  id: string
  tool: string
  source_filename: string
  user_email: string
  user_id: string
  user_name?: string
  created_at: string
  status: string
  total_count?: number
  success_count?: number
  error_count?: number
}

const toolColors: Record<string, string> = {
  extract: 'bg-blue-100 text-blue-700',
  title: 'bg-green-100 text-green-700',
  proration: 'bg-purple-100 text-purple-700',
  revenue: 'bg-amber-100 text-amber-700',
  ghl_prep: 'bg-orange-100 text-orange-700',
}

const toolPaths: Record<string, string> = {
  extract: '/extract',
  title: '/title',
  proration: '/proration',
  revenue: '/revenue',
  ghl_prep: '/ghl-prep',
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [recentJobs, setRecentJobs] = useState<RecentJob[]>([])
  const [toolCounts, setToolCounts] = useState<Record<string, number>>({})

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const response = await fetch(`${API_BASE}/history/jobs?limit=50`)
        if (!response.ok) return
        const data = await response.json()
        const jobs: RecentJob[] = data.jobs || []
        setRecentJobs(jobs.slice(0, 20))

        const counts: Record<string, number> = {}
        for (const job of jobs) {
          counts[job.tool] = (counts[job.tool] || 0) + 1
        }
        setToolCounts(counts)
      } catch {
        // Silently fail
      }
    }
    fetchJobs()
  }, [])

  const totalJobs = Object.values(toolCounts).reduce((sum, c) => sum + c, 0)

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
          {toolConfigs.map((tool) => (
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
                  <p className="text-2xl font-oswald font-semibold text-tre-navy">{toolCounts[tool.tool] || 0}</p>
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
          {recentJobs.length === 0 ? (
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
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Date & Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentJobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => navigate(toolPaths[job.tool] || '/')}
                    className="hover:bg-gray-50 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${toolColors[job.tool] || 'bg-gray-100 text-gray-700'}`}>
                        {job.tool.charAt(0).toUpperCase() + job.tool.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">{job.source_filename || 'Unknown'}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{job.user_name || job.user_id || job.user_email || 'Unknown'}</td>
                    <td className="px-4 py-3">
                      {job.status === 'completed' ? (
                        <span className="inline-flex items-center gap-1 text-green-600 text-xs">
                          <CheckCircle className="w-3.5 h-3.5" />
                          {job.total_count ? `${job.total_count} rows` : 'Done'}
                        </span>
                      ) : job.status === 'failed' ? (
                        <span className="inline-flex items-center gap-1 text-red-600 text-xs">
                          <XCircle className="w-3.5 h-3.5" />
                          Failed
                        </span>
                      ) : (
                        <span className="text-gray-500 text-xs">{job.status || '\u2014'}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {job.created_at ? new Date(job.created_at).toLocaleString() : ''}
                    </td>
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
