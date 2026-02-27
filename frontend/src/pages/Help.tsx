import { HelpCircle, Book, MessageCircle, Mail, ExternalLink, Search, Settings, ChevronDown } from 'lucide-react'
import { useState } from 'react'

const ghlSetupSteps = [
  {
    title: 'Creating a Private Integration Token',
    content: `1. Log in to your GoHighLevel sub-account\n2. Go to Settings → Integrations → API Keys\n3. Click "Create Token" or "Add API Key"\n4. Give it a descriptive name (e.g., "Table Rock Tools")\n5. Copy the token — it will only be shown once\n6. Store it securely; you'll enter it in Settings below`
  },
  {
    title: 'Finding Your Location ID',
    content: `1. Log in to your GoHighLevel sub-account\n2. Go to Settings → Business Profile (or Settings → Company)\n3. Look for "Location ID" or "Company ID" — it's a string like "abc123XYZ"\n4. Copy this ID; you'll need it when adding a connection in Settings`
  },
  {
    title: 'Adding a Connection in Settings',
    content: `1. In Table Rock Tools, go to Settings → GHL Connections\n2. Click "Add Connection"\n3. Enter a name for the connection (e.g., "Main Sub-Account")\n4. Paste the Private Integration Token\n5. Paste the Location ID\n6. Click Save — the system will validate your credentials immediately\n7. If validation fails, double-check the token and Location ID`
  },
  {
    title: 'Sending Your First Batch',
    content: `1. Process your data through the GHL Prep tool\n2. Review the preview table for accuracy\n3. Click "Send to GHL" next to the Download CSV button\n4. Select your sub-account connection\n5. Enter a campaign tag (required — used for filtering in GHL)\n6. Optionally select 1-2 contact owners\n7. Click "Validate & Send" to check your data\n8. Confirm to start sending — you'll see real-time progress\n9. After completion, review the summary for any failed contacts`
  },
]

const ghlFaqs = [
  {
    question: 'Why is the Send to GHL button disabled?',
    answer: 'The button is disabled when no valid GHL connection is configured. Go to Settings → GHL Connections to add or fix your connection. Make sure the connection shows a "Valid" status after saving.'
  },
  {
    question: 'Why did some contacts fail?',
    answer: 'Common reasons: invalid phone number format (must be valid US number), missing required fields (need at least email or phone), duplicate contacts that couldn\'t be merged, or temporary GHL API errors. Check the error details in the failed contacts view for specific reasons.'
  },
  {
    question: 'What does "Daily limit reached" mean?',
    answer: 'GoHighLevel has a daily API limit of 200,000 requests. If you hit this limit mid-batch, the remaining contacts are saved and can be sent after midnight UTC. The daily capacity counter near the Send button shows your remaining allowance.'
  },
  {
    question: 'How does contact owner assignment work?',
    answer: 'You can select 1-2 contact owners from the sub-account\'s GHL users. If you select 2 owners, contacts are split evenly (first half to Owner A, second half to Owner B). Owner assignment only applies to contacts that don\'t already have an owner in GHL — existing owner assignments are never overwritten.'
  },
  {
    question: 'What happens if I close the page during a send?',
    answer: 'The send continues on the server even if you close the page. When you return to the GHL Prep page, it will detect the active send and reconnect to show progress. You can also cancel the send from the progress view.'
  },
  {
    question: 'How do I retry failed contacts?',
    answer: 'After a send completes, click "View Failed Contacts" in the summary. This loads the failed contacts with error details. You can exclude specific rows, then click "Retry Send" to re-send the remaining failed contacts.'
  },
]

const fieldMapping = [
  { csv: 'Mineral Contact System Id', ghl: 'Custom Field (mineralContactSystemId)', required: true, notes: 'Unique identifier for upsert matching' },
  { csv: 'First Name', ghl: 'firstName', required: false, notes: '' },
  { csv: 'Last Name', ghl: 'lastName', required: false, notes: '' },
  { csv: 'Email', ghl: 'email', required: false, notes: 'At least email or phone required' },
  { csv: 'Phone', ghl: 'phone', required: false, notes: 'Normalized to E.164 format (+1XXXXXXXXXX)' },
  { csv: 'Address 1', ghl: 'address1', required: false, notes: '' },
  { csv: 'City', ghl: 'city', required: false, notes: '' },
  { csv: 'State', ghl: 'state', required: false, notes: '' },
  { csv: 'Postal Code', ghl: 'postalCode', required: false, notes: '' },
]

const faqs = [
  {
    question: 'How do I upload documents for extraction?',
    answer:
      'Navigate to the Extract tool, then drag and drop your PDF or document files into the upload area. You can also click to browse and select files from your computer.',
  },
  {
    question: 'What file formats are supported?',
    answer:
      'We support PDF, DOCX, DOC, XLSX, XLS, and CSV files. For best results with document extraction, PDF files are recommended.',
  },
  {
    question: 'How long does document processing take?',
    answer:
      'Processing time depends on document size and complexity. Most documents are processed within 1-5 minutes. Large or complex documents may take longer.',
  },
  {
    question: 'Can I export my data?',
    answer:
      'Yes, all tools support exporting data. Look for the Download or Export button in each tool to save your results as CSV, Excel, or PDF files.',
  },
  {
    question: 'How is proration calculated?',
    answer:
      'Proration calculations are based on the effective date and interest percentages you provide. The system automatically allocates interests according to standard mineral interest proration rules.',
  },
]

const resources = [
  {
    title: 'Getting Started Guide',
    description: 'Learn the basics of using Table Rock Tools',
    icon: Book,
    link: '#',
  },
  {
    title: 'Video Tutorials',
    description: 'Watch step-by-step tutorials for each tool',
    icon: ExternalLink,
    link: '#',
  },
  {
    title: 'Contact Support',
    description: 'Reach out to our support team',
    icon: Mail,
    link: 'mailto:support@tablerockenergy.com',
  },
]

export default function Help() {
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedFaq, setExpandedFaq] = useState<number | null>(null)
  const [openGhlStep, setOpenGhlStep] = useState<number | null>(null)
  const [openGhlFaq, setOpenGhlFaq] = useState<number | null>(null)

  const filteredFaqs = faqs.filter(
    (faq) =>
      faq.question.toLowerCase().includes(searchQuery.toLowerCase()) ||
      faq.answer.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-gray-100 rounded-lg">
          <HelpCircle className="w-6 h-6 text-gray-600" />
        </div>
        <div>
          <h1 className="text-2xl font-oswald font-semibold text-tre-navy">
            Help Center
          </h1>
          <p className="text-gray-500 text-sm">
            Find answers and get support
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-xl font-oswald font-semibold text-tre-navy mb-2">
            How can we help you?
          </h2>
          <p className="text-gray-500 mb-4">
            Search our knowledge base or browse frequently asked questions
          </p>
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search for help..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-tre-teal/50 focus:border-tre-teal text-lg"
            />
          </div>
        </div>
      </div>

      {/* GHL Integration Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-tre-teal/10 rounded-lg">
            <Settings className="w-6 h-6 text-tre-teal" />
          </div>
          <h2 className="text-lg font-oswald font-semibold text-tre-navy">
            GHL Integration
          </h2>
        </div>

        <div className="space-y-8">
          {/* Setup Guide */}
          <div>
            <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide mb-4">
              Setup Guide
            </h3>
            <div className="space-y-2">
              {ghlSetupSteps.map((step, index) => (
                <div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setOpenGhlStep(openGhlStep === index ? null : index)}
                    className="w-full flex items-center justify-between p-4 text-left bg-white hover:bg-gray-50 transition-colors"
                  >
                    <span className="font-medium text-gray-900">
                      {step.title}
                    </span>
                    <ChevronDown
                      className={`w-5 h-5 text-tre-teal transition-transform ${
                        openGhlStep === index ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  {openGhlStep === index && (
                    <div className="px-4 pb-4 text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                      {step.content}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Field Mapping */}
          <div>
            <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide mb-4">
              Field Mapping
            </h3>
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-tre-navy/5">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium text-gray-700">CSV Column</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-700">GHL Field</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-700">Required</th>
                    <th className="text-left px-3 py-2 font-medium text-gray-700">Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {fieldMapping.map((field, index) => (
                    <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}>
                      <td className="px-3 py-2 text-gray-900">{field.csv}</td>
                      <td className="px-3 py-2 text-gray-700 font-mono">{field.ghl}</td>
                      <td className="px-3 py-2">
                        {field.required ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            Required
                          </span>
                        ) : (
                          <span className="text-gray-500">Optional</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-gray-600">{field.notes}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Troubleshooting */}
          <div>
            <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide mb-4">
              Troubleshooting
            </h3>
            <div className="space-y-2">
              {ghlFaqs.map((faq, index) => (
                <div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setOpenGhlFaq(openGhlFaq === index ? null : index)}
                    className="w-full flex items-center justify-between p-4 text-left bg-white hover:bg-gray-50 transition-colors"
                  >
                    <span className="font-medium text-gray-900">
                      {faq.question}
                    </span>
                    <ChevronDown
                      className={`w-5 h-5 text-tre-teal transition-transform ${
                        openGhlFaq === index ? 'rotate-180' : ''
                      }`}
                    />
                  </button>
                  {openGhlFaq === index && (
                    <div className="px-4 pb-4 text-sm text-gray-600 leading-relaxed">
                      {faq.answer}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* FAQs */}
        <div className="lg:col-span-2">
          <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
            Frequently Asked Questions
          </h2>
          <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
            {filteredFaqs.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No results found for "{searchQuery}"
              </div>
            ) : (
              filteredFaqs.map((faq, index) => (
                <div key={index} className="p-4">
                  <button
                    onClick={() => setExpandedFaq(expandedFaq === index ? null : index)}
                    className="w-full flex items-start justify-between text-left"
                  >
                    <span className="font-medium text-gray-900 pr-4">
                      {faq.question}
                    </span>
                    <span
                      className={`text-tre-teal transition-transform ${
                        expandedFaq === index ? 'rotate-180' : ''
                      }`}
                    >
                      <svg
                        className="w-5 h-5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </span>
                  </button>
                  {expandedFaq === index && (
                    <div className="mt-3 text-gray-600 text-sm leading-relaxed">
                      {faq.answer}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Resources */}
        <div>
          <h2 className="text-lg font-oswald font-semibold text-tre-navy mb-4">
            Resources
          </h2>
          <div className="space-y-4">
            {resources.map((resource, index) => (
              <a
                key={index}
                href={resource.link}
                className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-tre-teal hover:shadow-md transition-all"
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-tre-teal/10 rounded-lg">
                    <resource.icon className="w-5 h-5 text-tre-teal" />
                  </div>
                  <div>
                    <h3 className="font-medium text-gray-900">{resource.title}</h3>
                    <p className="text-sm text-gray-500">{resource.description}</p>
                  </div>
                </div>
              </a>
            ))}
          </div>

          {/* Contact Card */}
          <div className="mt-6 bg-tre-navy rounded-xl p-6 text-white">
            <MessageCircle className="w-8 h-8 text-tre-teal mb-3" />
            <h3 className="font-oswald font-semibold text-lg mb-2">
              Need more help?
            </h3>
            <p className="text-tre-teal/80 text-sm mb-4">
              Our support team is here to assist you with any questions.
            </p>
            <a
              href="mailto:support@tablerockenergy.com"
              className="inline-flex items-center gap-2 px-4 py-2 bg-tre-teal text-tre-navy rounded-lg font-medium hover:bg-tre-teal/90 transition-colors"
            >
              <Mail className="w-4 h-4" />
              Contact Support
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
