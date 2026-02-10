import { useState, useEffect } from 'react'
import { Search, Phone, Mail, Globe, AlertTriangle, X, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import { enrichmentApi, type EnrichedPerson, type EnrichmentStatusResponse } from '../utils/api'

interface PersonInput {
  name: string
  address?: string
  city?: string
  state?: string
  zip_code?: string
}

interface EnrichmentPanelProps {
  persons: PersonInput[]
  isOpen: boolean
  onClose: () => void
}

export default function EnrichmentPanel({ persons, isOpen, onClose }: EnrichmentPanelProps) {
  const [status, setStatus] = useState<EnrichmentStatusResponse | null>(null)
  const [results, setResults] = useState<EnrichedPerson[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)
  const [hasSearched, setHasSearched] = useState(false)

  useEffect(() => {
    if (isOpen) {
      enrichmentApi.getStatus().then(({ data }) => {
        if (data) setStatus(data)
      })
    }
  }, [isOpen])

  const handleEnrich = async () => {
    if (!persons.length) return

    setIsLoading(true)
    setError('')
    setResults([])
    setHasSearched(true)

    try {
      const { data, error: apiError } = await enrichmentApi.lookup(persons)
      if (apiError) {
        setError(apiError)
      } else if (data) {
        if (!data.success) {
          setError(data.error_message || 'Enrichment failed')
        } else {
          setResults(data.results)
        }
      }
    } catch {
      setError('Failed to connect to enrichment service')
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) return null

  const notConfigured = status && !status.enabled

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex justify-end">
      <div className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col animate-in slide-in-from-right">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-tre-navy">
          <div className="flex items-center gap-3">
            <Search className="w-5 h-5 text-tre-teal" />
            <div>
              <h2 className="text-lg font-oswald font-semibold text-white">Data Enrichment</h2>
              <p className="text-xs text-gray-300">
                {persons.length} {persons.length === 1 ? 'person' : 'persons'} selected
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-300 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {notConfigured ? (
            <div className="text-center py-12">
              <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Enrichment Not Configured</h3>
              <p className="text-sm text-gray-500 mb-4">
                You need to add API keys in Settings before using enrichment.
              </p>
              <a
                href="/settings"
                className="inline-flex items-center gap-2 px-4 py-2 bg-tre-navy text-white rounded-lg hover:bg-tre-navy/90 transition-colors text-sm"
              >
                Go to Settings
                <ExternalLink className="w-4 h-4" />
              </a>
            </div>
          ) : (
            <>
              {/* Enrich Button */}
              {!hasSearched && (
                <div className="text-center py-8">
                  <p className="text-sm text-gray-500 mb-4">
                    Enrich {persons.length} {persons.length === 1 ? 'person' : 'persons'} with phone numbers, emails, social media, and public records.
                  </p>
                  <button
                    onClick={handleEnrich}
                    disabled={isLoading}
                    className="px-6 py-3 bg-tre-teal text-white rounded-lg hover:bg-tre-teal/90 transition-colors disabled:opacity-50 font-oswald tracking-wide"
                  >
                    {isLoading ? (
                      <span className="flex items-center gap-2">
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Enriching...
                      </span>
                    ) : (
                      <span className="flex items-center gap-2">
                        <Search className="w-4 h-4" />
                        Enrich Selected
                      </span>
                    )}
                  </button>
                  {status && (
                    <div className="mt-4 flex justify-center gap-4 text-xs text-gray-400">
                      {status.pdl_configured && <span>PDL: Active</span>}
                      {status.searchbug_configured && <span>SearchBug: Active</span>}
                    </div>
                  )}
                </div>
              )}

              {/* Loading */}
              {isLoading && hasSearched && (
                <div className="text-center py-12">
                  <div className="w-8 h-8 border-3 border-tre-teal border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                  <p className="text-sm text-gray-500">Looking up {persons.length} {persons.length === 1 ? 'person' : 'persons'}...</p>
                  <p className="text-xs text-gray-400 mt-1">This may take a moment per person</p>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg mb-4">
                  <p className="text-sm text-red-700">{error}</p>
                  <button
                    onClick={handleEnrich}
                    className="mt-2 text-sm text-red-600 underline hover:no-underline"
                  >
                    Try again
                  </button>
                </div>
              )}

              {/* Results */}
              {results.length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm text-gray-500">
                      {results.filter(r => r.enrichment_sources.length > 0).length} of {results.length} enriched
                    </p>
                    <button
                      onClick={handleEnrich}
                      disabled={isLoading}
                      className="text-sm text-tre-teal hover:underline disabled:opacity-50"
                    >
                      Re-run
                    </button>
                  </div>

                  {results.map((person, idx) => (
                    <PersonCard
                      key={idx}
                      person={person}
                      isExpanded={expandedIdx === idx}
                      onToggle={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}


function PersonCard({
  person,
  isExpanded,
  onToggle,
}: {
  person: EnrichedPerson
  isExpanded: boolean
  onToggle: () => void
}) {
  const hasData = person.enrichment_sources.length > 0
  const hasFlags = person.public_records?.is_deceased || person.public_records?.has_bankruptcy || person.public_records?.has_liens

  return (
    <div className={`border rounded-lg overflow-hidden ${hasFlags ? 'border-amber-300 bg-amber-50/30' : 'border-gray-200'}`}>
      {/* Header row — always visible */}
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-900 truncate">{person.original_name}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
            {person.phones.length > 0 && (
              <span className="flex items-center gap-1"><Phone className="w-3 h-3" /> {person.phones.length}</span>
            )}
            {person.emails.length > 0 && (
              <span className="flex items-center gap-1"><Mail className="w-3 h-3" /> {person.emails.length}</span>
            )}
            {person.social_profiles.length > 0 && (
              <span className="flex items-center gap-1"><Globe className="w-3 h-3" /> {person.social_profiles.length}</span>
            )}
            {hasFlags && (
              <span className="flex items-center gap-1 text-amber-600"><AlertTriangle className="w-3 h-3" /> Flags</span>
            )}
            {!hasData && (
              <span className="text-gray-400 italic">No data found</span>
            )}
          </div>
        </div>
        <div className="ml-2 flex items-center gap-2">
          {person.match_confidence && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              person.match_confidence === 'high' ? 'bg-green-100 text-green-700' :
              person.match_confidence === 'medium' ? 'bg-yellow-100 text-yellow-700' :
              'bg-gray-100 text-gray-500'
            }`}>
              {person.match_confidence}
            </span>
          )}
          {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </button>

      {/* Expanded details */}
      {isExpanded && hasData && (
        <div className="px-4 pb-4 space-y-4 border-t border-gray-100">
          {/* Phones */}
          {person.phones.length > 0 && (
            <div className="pt-3">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Phone Numbers</p>
              <div className="space-y-1">
                {person.phones.map((ph, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <Phone className="w-3.5 h-3.5 text-gray-400" />
                    <span className="font-mono">{ph.number}</span>
                    {ph.type && <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{ph.type}</span>}
                    {ph.carrier && <span className="text-xs text-gray-400">{ph.carrier}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Emails */}
          {person.emails.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Email Addresses</p>
              <div className="space-y-1">
                {person.emails.map((em, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <Mail className="w-3.5 h-3.5 text-gray-400" />
                    <span>{em}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Social */}
          {person.social_profiles.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Social Media</p>
              <div className="space-y-1">
                {person.social_profiles.map((sp, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    <Globe className="w-3.5 h-3.5 text-gray-400" />
                    <a
                      href={sp.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-tre-teal hover:underline"
                    >
                      {sp.platform}{sp.username ? ` (@${sp.username})` : ''}
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Public Records */}
          {hasFlags && person.public_records && (
            <div>
              <p className="text-xs font-semibold text-amber-600 uppercase tracking-wider mb-2">Public Records</p>
              <div className="space-y-2">
                {person.public_records.is_deceased && (
                  <div className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 p-2 rounded">
                    <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium">Deceased</p>
                      {person.public_records.deceased_date && (
                        <p className="text-xs text-amber-600">Date: {person.public_records.deceased_date}</p>
                      )}
                    </div>
                  </div>
                )}
                {person.public_records.has_bankruptcy && (
                  <div className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 p-2 rounded">
                    <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium">Bankruptcy</p>
                      {person.public_records.bankruptcy_details.map((d, i) => (
                        <p key={i} className="text-xs text-amber-600">{d}</p>
                      ))}
                    </div>
                  </div>
                )}
                {person.public_records.has_liens && (
                  <div className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 p-2 rounded">
                    <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="font-medium">Liens / Judgments</p>
                      {person.public_records.lien_details.map((d, i) => (
                        <p key={i} className="text-xs text-amber-600">{d}</p>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Sources */}
          <div className="pt-2 border-t border-gray-100">
            <p className="text-xs text-gray-400">
              Sources: {person.enrichment_sources.join(', ')}
              {person.enriched_at && ` | ${new Date(person.enriched_at).toLocaleString()}`}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
