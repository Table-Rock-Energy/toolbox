import { CheckCircle, Clock, AlertCircle, XCircle, Loader } from 'lucide-react'

type StatusType = 'success' | 'pending' | 'processing' | 'warning' | 'error'

interface StatusBadgeProps {
  status: StatusType
  label?: string
  size?: 'sm' | 'md' | 'lg'
}

const statusConfig: Record<StatusType, {
  icon: typeof CheckCircle
  bgColor: string
  textColor: string
  borderColor: string
  defaultLabel: string
}> = {
  success: {
    icon: CheckCircle,
    bgColor: 'bg-green-50',
    textColor: 'text-green-700',
    borderColor: 'border-green-200',
    defaultLabel: 'Complete',
  },
  pending: {
    icon: Clock,
    bgColor: 'bg-yellow-50',
    textColor: 'text-yellow-700',
    borderColor: 'border-yellow-200',
    defaultLabel: 'Pending',
  },
  processing: {
    icon: Loader,
    bgColor: 'bg-blue-50',
    textColor: 'text-blue-700',
    borderColor: 'border-blue-200',
    defaultLabel: 'Processing',
  },
  warning: {
    icon: AlertCircle,
    bgColor: 'bg-orange-50',
    textColor: 'text-orange-700',
    borderColor: 'border-orange-200',
    defaultLabel: 'Warning',
  },
  error: {
    icon: XCircle,
    bgColor: 'bg-red-50',
    textColor: 'text-red-700',
    borderColor: 'border-red-200',
    defaultLabel: 'Error',
  },
}

const sizeConfig = {
  sm: {
    padding: 'px-2 py-0.5',
    iconSize: 'w-3 h-3',
    textSize: 'text-xs',
    gap: 'gap-1',
  },
  md: {
    padding: 'px-2.5 py-1',
    iconSize: 'w-4 h-4',
    textSize: 'text-sm',
    gap: 'gap-1.5',
  },
  lg: {
    padding: 'px-3 py-1.5',
    iconSize: 'w-5 h-5',
    textSize: 'text-base',
    gap: 'gap-2',
  },
}

export default function StatusBadge({
  status,
  label,
  size = 'md',
}: StatusBadgeProps) {
  const config = statusConfig[status]
  const sizeStyles = sizeConfig[size]
  const Icon = config.icon

  return (
    <span
      className={`inline-flex items-center ${sizeStyles.gap} ${sizeStyles.padding} ${config.bgColor} ${config.textColor} border ${config.borderColor} rounded-full font-medium ${sizeStyles.textSize}`}
    >
      <Icon className={`${sizeStyles.iconSize} ${status === 'processing' ? 'animate-spin' : ''}`} />
      {label || config.defaultLabel}
    </span>
  )
}
