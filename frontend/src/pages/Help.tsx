import { HelpCircle, Book, MessageCircle, Mail, ExternalLink, Search } from 'lucide-react'
import { useState } from 'react'

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
