import { useOperationState } from '../contexts/OperationContext'
import { useNavigate, useLocation } from 'react-router-dom'
import { Loader2, CheckCircle2 } from 'lucide-react'
import type { OperationState } from '../contexts/OperationContext'
import type { PipelineStep } from '../hooks/useEnrichmentPipeline'

const TOOL_ROUTES: Record<string, string> = {
  extract: '/extract',
  ecf: '/extract',
  title: '/title',
  proration: '/proration',
  revenue: '/revenue',
}

const TOOL_LABELS: Record<string, string> = {
  extract: 'Extract',
  ecf: 'Extract',
  title: 'Title',
  proration: 'Proration',
  revenue: 'Revenue',
}

const STEP_LABELS: Record<PipelineStep, string> = {
  cleanup: 'Clean Up',
  validate: 'Validate',
  enrich: 'Enrich',
}

function deriveLabel(operation: OperationState): string {
  const toolLabel = TOOL_LABELS[operation.tool] ?? operation.tool

  if (operation.status === 'completed') {
    return `${toolLabel}: Complete`
  }

  if (operation.batchProgress) {
    const { currentStep, currentBatch, totalBatches } = operation.batchProgress
    const stepLabel = STEP_LABELS[currentStep] ?? currentStep
    return `${toolLabel}: ${stepLabel} ${currentBatch}/${totalBatches}`
  }

  return `${toolLabel}: Processing...`
}

export default function OperationStatusBar() {
  const operation = useOperationState()
  const navigate = useNavigate()
  const location = useLocation()

  if (!operation || operation.status === 'idle') return null

  // Hide when user is already on the tool's page (modal shows instead)
  const toolRoute = TOOL_ROUTES[operation.tool]
  if (toolRoute && location.pathname === toolRoute) return null

  const isCompleted = operation.status === 'completed'
  const label = deriveLabel(operation)

  const handleClick = () => {
    if (toolRoute) {
      navigate(toolRoute)
    }
  }

  return (
    <div
      onClick={handleClick}
      className={`cursor-pointer h-8 flex items-center justify-center gap-2 text-sm font-oswald tracking-wide ${
        isCompleted
          ? 'bg-emerald-500 text-white transition-colors duration-300'
          : 'bg-tre-teal/90 text-white animate-status-shimmer'
      }`}
    >
      {isCompleted ? (
        <CheckCircle2 className="w-4 h-4" />
      ) : (
        <Loader2 className="w-4 h-4 animate-spin" />
      )}
      <span>{label}</span>
    </div>
  )
}
