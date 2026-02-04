import { useCallback, useState } from 'react'
import { Upload, File, X, CheckCircle, AlertCircle } from 'lucide-react'

interface FileUploadProps {
  onFilesSelected: (files: File[]) => void
  accept?: string
  multiple?: boolean
  maxSize?: number // in MB
  label?: string
  description?: string
}

interface UploadedFile {
  file: File
  status: 'pending' | 'uploading' | 'success' | 'error'
  progress?: number
  error?: string
}

export default function FileUpload({
  onFilesSelected,
  accept = '.pdf,.xlsx,.xls,.csv',
  multiple = true,
  maxSize = 50,
  label = 'Upload Files',
  description = 'Drag and drop files here, or click to select',
}: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const validateFiles = (files: File[]): File[] => {
    return files.filter((file) => {
      if (file.size > maxSize * 1024 * 1024) {
        console.warn(`File ${file.name} exceeds ${maxSize}MB limit`)
        return false
      }
      return true
    })
  }

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      const files = Array.from(e.dataTransfer.files)
      const validFiles = validateFiles(files)
      if (validFiles.length > 0) {
        const newUploadedFiles = validFiles.map((file) => ({
          file,
          status: 'pending' as const,
        }))
        setUploadedFiles((prev) => [...prev, ...newUploadedFiles])
        onFilesSelected(validFiles)
      }
    },
    [onFilesSelected, maxSize]
  )

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || [])
      const validFiles = validateFiles(files)
      if (validFiles.length > 0) {
        const newUploadedFiles = validFiles.map((file) => ({
          file,
          status: 'pending' as const,
        }))
        setUploadedFiles((prev) => [...prev, ...newUploadedFiles])
        onFilesSelected(validFiles)
      }
    },
    [onFilesSelected, maxSize]
  )

  const removeFile = (index: number) => {
    setUploadedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const getStatusIcon = (status: UploadedFile['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      default:
        return <File className="w-4 h-4 text-tre-brown-medium" />
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-gray-700">{label}</label>

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all duration-200 ${
          isDragging
            ? 'border-tre-teal bg-tre-teal/5'
            : 'border-gray-300 hover:border-tre-teal/50 hover:bg-gray-50'
        }`}
      >
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleFileSelect}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />

        <div className="flex flex-col items-center gap-3">
          <div className={`p-3 rounded-full transition-colors ${
            isDragging ? 'bg-tre-teal/20' : 'bg-gray-100'
          }`}>
            <Upload className={`w-8 h-8 ${isDragging ? 'text-tre-teal' : 'text-gray-400'}`} />
          </div>
          <div>
            <p className="text-gray-600">{description}</p>
            <p className="text-sm text-gray-400 mt-1">
              Accepts: {accept} (max {maxSize}MB)
            </p>
          </div>
        </div>
      </div>

      {uploadedFiles.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-700">
            Selected Files ({uploadedFiles.length})
          </p>
          <div className="space-y-2">
            {uploadedFiles.map((uploadedFile, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200"
              >
                {getStatusIcon(uploadedFile.status)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-700 truncate">
                    {uploadedFile.file.name}
                  </p>
                  <p className="text-xs text-gray-400">
                    {formatFileSize(uploadedFile.file.size)}
                  </p>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="p-1 hover:bg-gray-200 rounded transition-colors"
                >
                  <X className="w-4 h-4 text-gray-400" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
