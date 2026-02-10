import { useState, useEffect } from 'react'
import {
  Search,
  Users,
  GitBranch,
  MapPin,
  ChevronRight,
  X,
  Database,
  CheckCircle,
  AlertCircle,
  Building2,
  User,
  Landmark,
  FileText,
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

// Types matching backend models
interface Entity {
  id: string
  canonical_name: string
  entity_type: string
  names: { name: string; is_primary: boolean }[]
  addresses: { street?: string; city?: string; state?: string; zip_code?: string }[]
  properties: { property_name?: string; county?: string; interest?: number; rrc_lease?: string }[]
  source_references: { tool: string; document?: string }[]
  first_name?: string
  last_name?: string
  confidence_score: number
  verification_status: string
  notes?: string
}

interface Relationship {
  id: string
  from_entity_id: string
  from_entity_name: string
  to_entity_id: string
  to_entity_name: string
  relationship_type: string
  verification_status: string
}

interface OwnershipRecord {
  id: string
  entity_name: string
  property_name?: string
  county?: string
  interest?: number
  interest_type?: string
  rrc_lease?: string
  operator?: string
  rrc_acres?: number
  est_nra?: number
  last_revenue_date?: string
  total_revenue?: number
}

interface PipelineStatus {
  total_entities: number
  total_relationships: number
  total_ownership_records: number
}

interface SearchResult {
  entity: Entity
  match_score: number
  match_reason: string
}

const entityTypeIcon = (type: string) => {
  switch (type) {
    case 'individual': return <User className="w-4 h-4" />
    case 'trust': return <Landmark className="w-4 h-4" />
    case 'estate': return <FileText className="w-4 h-4" />
    case 'llc':
    case 'corporation':
    case 'partnership':
    case 'mineral_co': return <Building2 className="w-4 h-4" />
    default: return <Users className="w-4 h-4" />
  }
}

const verificationBadge = (status: string) => {
  switch (status) {
    case 'user_verified':
    case 'user_corrected':
      return <span className="inline-flex items-center gap-1 text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full"><CheckCircle className="w-3 h-3" /> Verified</span>
    case 'high_confidence':
      return <span className="inline-flex items-center gap-1 text-xs bg-tre-teal/20 text-tre-teal px-2 py-0.5 rounded-full"><CheckCircle className="w-3 h-3" /> High Confidence</span>
    case 'disputed':
      return <span className="inline-flex items-center gap-1 text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full"><AlertCircle className="w-3 h-3" /> Disputed</span>
    default:
      return <span className="text-xs bg-gray-500/20 text-gray-400 px-2 py-0.5 rounded-full">Inferred</span>
  }
}

export default function MineralRights() {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null)
  const [relationships, setRelationships] = useState<Relationship[]>([])
  const [ownershipRecords, setOwnershipRecords] = useState<OwnershipRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)

  // Load pipeline status on mount
  useEffect(() => {
    fetchStatus()
  }, [])

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/etl/status`)
      if (res.ok) {
        setStatus(await res.json())
      }
    } catch (e) {
      console.error('Failed to fetch ETL status:', e)
    }
  }

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setSearchLoading(true)
    try {
      const res = await fetch(`${API_BASE}/etl/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, limit: 20 }),
      })
      if (res.ok) {
        const data = await res.json()
        setSearchResults(data.results || [])
        setSelectedEntity(null)
      }
    } catch (e) {
      console.error('Search failed:', e)
    } finally {
      setSearchLoading(false)
    }
  }

  const selectEntity = async (entityId: string) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/etl/entities/${entityId}`)
      if (res.ok) {
        const data = await res.json()
        setSelectedEntity(data.entity)
        setRelationships(data.relationships || [])
        setOwnershipRecords(data.ownership_records || [])
        setRelatedEntities(data.related_entities || [])
      }
    } catch (e) {
      console.error('Failed to fetch entity:', e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-oswald font-semibold text-white">
          Bronze Database
        </h1>
        <p className="text-gray-400 mt-1">
          Raw entity ingestion layer — mineral rights ownership, inheritance chains, and property interests
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-tre-navy/50 border border-tre-teal/20 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-tre-teal/10 rounded-lg">
              <Users className="w-5 h-5 text-tre-teal" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-white">
                {status?.total_entities ?? '—'}
              </p>
              <p className="text-xs text-gray-400 uppercase tracking-wider">Entities</p>
            </div>
          </div>
        </div>
        <div className="bg-tre-navy/50 border border-tre-teal/20 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-tre-teal/10 rounded-lg">
              <GitBranch className="w-5 h-5 text-tre-teal" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-white">
                {status?.total_relationships ?? '—'}
              </p>
              <p className="text-xs text-gray-400 uppercase tracking-wider">Relationships</p>
            </div>
          </div>
        </div>
        <div className="bg-tre-navy/50 border border-tre-teal/20 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-tre-teal/10 rounded-lg">
              <MapPin className="w-5 h-5 text-tre-teal" />
            </div>
            <div>
              <p className="text-2xl font-oswald font-semibold text-white">
                {status?.total_ownership_records ?? '—'}
              </p>
              <p className="text-xs text-gray-400 uppercase tracking-wider">Ownership Records</p>
            </div>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="bg-tre-navy/50 border border-tre-teal/20 rounded-lg p-6">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search by name, property, or county..."
              className="w-full pl-10 pr-4 py-3 bg-tre-navy border border-tre-teal/30 rounded-lg text-white placeholder-gray-500 font-oswald focus:outline-none focus:border-tre-teal transition-colors"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searchLoading}
            className="px-6 py-3 bg-tre-teal/20 text-tre-teal border border-tre-teal/30 rounded-lg font-oswald hover:bg-tre-teal/30 transition-colors disabled:opacity-50"
          >
            {searchLoading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="mt-4 space-y-2">
            <p className="text-sm text-gray-400">
              {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} found
            </p>
            <div className="space-y-1">
              {searchResults.map((result) => (
                <button
                  key={result.entity.id}
                  onClick={() => selectEntity(result.entity.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-left transition-colors ${
                    selectedEntity?.id === result.entity.id
                      ? 'bg-tre-teal/20 border border-tre-teal/40'
                      : 'hover:bg-tre-navy/80 border border-transparent'
                  }`}
                >
                  <div className="text-tre-teal">
                    {entityTypeIcon(result.entity.entity_type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-oswald truncate">
                      {result.entity.canonical_name}
                    </p>
                    <p className="text-xs text-gray-400 capitalize">
                      {result.entity.entity_type.replace('_', ' ')} · {result.match_reason}
                    </p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-tre-teal">
                      {Math.round(result.match_score * 100)}%
                    </span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-500" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Entity Detail Panel */}
      {selectedEntity && (
        <div className="bg-tre-navy/50 border border-tre-teal/20 rounded-lg overflow-hidden">
          {loading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-tre-teal mx-auto" />
            </div>
          ) : (
            <>
              {/* Entity Header */}
              <div className="p-6 border-b border-tre-teal/20">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-tre-teal/10 rounded-lg text-tre-teal">
                      {entityTypeIcon(selectedEntity.entity_type)}
                    </div>
                    <div>
                      <h2 className="text-xl font-oswald font-semibold text-white">
                        {selectedEntity.canonical_name}
                      </h2>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-400 capitalize">
                          {selectedEntity.entity_type.replace('_', ' ')}
                        </span>
                        {verificationBadge(selectedEntity.verification_status)}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedEntity(null)}
                    className="text-gray-500 hover:text-gray-300"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 lg:gap-0 divide-y lg:divide-y-0 lg:divide-x divide-tre-teal/20">
                {/* Left Column: Names, Addresses, Sources */}
                <div className="p-6 space-y-6">
                  {/* Known Names */}
                  {selectedEntity.names.length > 0 && (
                    <div>
                      <h3 className="text-sm font-oswald uppercase tracking-wider text-tre-tan/60 mb-2">
                        Known Names
                      </h3>
                      <ul className="space-y-1">
                        {selectedEntity.names.map((n, i) => (
                          <li key={i} className="flex items-center gap-2 text-sm text-gray-300">
                            {n.is_primary && <span className="text-tre-teal text-xs">(primary)</span>}
                            {n.name}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Addresses */}
                  {selectedEntity.addresses.length > 0 && (
                    <div>
                      <h3 className="text-sm font-oswald uppercase tracking-wider text-tre-tan/60 mb-2">
                        Addresses
                      </h3>
                      <ul className="space-y-2">
                        {selectedEntity.addresses.map((a, i) => (
                          <li key={i} className="text-sm text-gray-300">
                            {a.street && <span>{a.street}<br /></span>}
                            {a.city && <span>{a.city}, </span>}
                            {a.state} {a.zip_code}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Data Sources */}
                  {selectedEntity.source_references.length > 0 && (
                    <div>
                      <h3 className="text-sm font-oswald uppercase tracking-wider text-tre-tan/60 mb-2">
                        Data Sources
                      </h3>
                      <ul className="space-y-1">
                        {selectedEntity.source_references.map((s, i) => (
                          <li key={i} className="text-xs text-gray-400">
                            <span className="capitalize text-tre-teal">{s.tool}</span>
                            {s.document && <span> · {s.document}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Right Column: Relationships, Properties */}
                <div className="p-6 space-y-6">
                  {/* Relationships */}
                  <div>
                    <h3 className="text-sm font-oswald uppercase tracking-wider text-tre-tan/60 mb-2">
                      Relationships ({relationships.length})
                    </h3>
                    {relationships.length > 0 ? (
                      <ul className="space-y-2">
                        {relationships.map((rel) => {
                          const isFrom = rel.from_entity_id === selectedEntity.id
                          const otherName = isFrom ? rel.to_entity_name : rel.from_entity_name
                          const otherId = isFrom ? rel.to_entity_id : rel.from_entity_id
                          return (
                            <li key={rel.id} className="flex items-center gap-2">
                              <GitBranch className="w-3 h-3 text-tre-tan" />
                              <button
                                onClick={() => selectEntity(otherId)}
                                className="text-sm text-tre-teal hover:underline"
                              >
                                {otherName}
                              </button>
                              <span className="text-xs text-gray-500 capitalize">
                                ({rel.relationship_type})
                              </span>
                            </li>
                          )
                        })}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-500">No relationships found yet</p>
                    )}
                  </div>

                  {/* Property Interests */}
                  <div>
                    <h3 className="text-sm font-oswald uppercase tracking-wider text-tre-tan/60 mb-2">
                      Property Interests ({ownershipRecords.length})
                    </h3>
                    {ownershipRecords.length > 0 ? (
                      <div className="space-y-2">
                        {ownershipRecords.map((rec) => (
                          <div
                            key={rec.id}
                            className="bg-tre-navy/80 rounded-lg p-3 border border-tre-teal/10"
                          >
                            <p className="text-sm text-white font-oswald">
                              {rec.property_name || 'Unknown Property'}
                            </p>
                            <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-400">
                              {rec.county && <span>{rec.county}</span>}
                              {rec.interest != null && (
                                <span>{(rec.interest * 100).toFixed(4)}% interest</span>
                              )}
                              {rec.rrc_lease && <span>RRC: {rec.rrc_lease}</span>}
                              {rec.operator && <span>Op: {rec.operator}</span>}
                              {rec.est_nra != null && (
                                <span>NRA: {rec.est_nra.toFixed(2)}</span>
                              )}
                              {rec.total_revenue != null && (
                                <span className="text-green-400">
                                  ${rec.total_revenue.toFixed(2)}
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">No ownership records yet</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Notes */}
              {selectedEntity.notes && (
                <div className="p-6 border-t border-tre-teal/20">
                  <h3 className="text-sm font-oswald uppercase tracking-wider text-tre-tan/60 mb-2">
                    Notes
                  </h3>
                  <p className="text-sm text-gray-300">{selectedEntity.notes}</p>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Empty State */}
      {!selectedEntity && searchResults.length === 0 && (
        <div className="bg-tre-navy/50 border border-tre-teal/20 rounded-lg p-12 text-center">
          <Database className="w-12 h-12 text-tre-teal/30 mx-auto mb-4" />
          <h3 className="text-lg font-oswald text-gray-400 mb-2">
            Search the Bronze Database
          </h3>
          <p className="text-sm text-gray-500 max-w-md mx-auto">
            As you process documents through Extract, Title, Proration, and Revenue,
            entities are automatically resolved and linked into this Bronze layer.
            Search by name to explore ownership records and inheritance chains.
          </p>
        </div>
      )}
    </div>
  )
}
