// Function to generate dynamic OG image URL
export function generateDynamicOGImage(pageData) {
  const baseUrl = 'https://dynamicog.com/og/docs/img'
  const logo = 'https://nexios-labs.github.io/nexios/logo.png'
  const website = 'nexios-labs.github.io'
  const name = 'Nexios Labs'

  // Extract title and description from page data
  let title = pageData?.title || pageData?.frontmatter?.title || 'Nexios'
  let sub = pageData?.description || pageData?.frontmatter?.description || 'Python Web Framework'

  // Handle different page types and improve titles
  const relativePath = pageData?.relativePath || ''

  // Extract title from first heading if no frontmatter title
  if (title === 'Nexios' && pageData?.content) {
    const headingMatch = pageData.content.match(/^#\s+(.+)$/m)
    if (headingMatch) {
      title = headingMatch[1].replace(/[🚀🤔⚡🔄🎯🌐🛣️📖🔐🐍📡🔌🏭]/g, '').trim()
    }
  }

  // Customize subtitle based on page location
  if (relativePath.includes('/guide/')) {
    if (sub === 'Python Web Framework') {
      sub = 'Guide - Learn Nexios'
    } else {
      sub = 'Guide - ' + sub
    }
  } else if (relativePath.includes('/intro/')) {
    if (sub === 'Python Web Framework') {
      sub = 'Introduction - Getting Started'
    } else {
      sub = 'Introduction - ' + sub
    }
  } else if (relativePath.includes('/community/')) {
    if (sub === 'Python Web Framework') {
      sub = 'Community - Extensions & Middleware'
    } else {
      sub = 'Community - ' + sub
    }
  } else if (relativePath.includes('/v2/')) {
    if (sub === 'Python Web Framework') {
      sub = 'v2 Documentation'
    } else {
      sub = 'v2 - ' + sub
    }
    if (!title.includes('v2')) {
      title = title + ' (v2)'
    }
  } else if (relativePath.includes('/howtos/')) {
    if (sub === 'Python Web Framework') {
      sub = 'How-to Guides'
    } else {
      sub = 'How-to - ' + sub
    }
  }

  // Fallback for pages without proper titles
  if (title === 'Nexios' && relativePath) {
    const pathParts = relativePath.replace('.md', '').split('/')
    const lastPart = pathParts[pathParts.length - 1]
    if (lastPart && lastPart !== 'index') {
      title = lastPart.split('-').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
      ).join(' ')
    } else if (pathParts.length > 1) {
      // Use parent directory name
      const parentDir = pathParts[pathParts.length - 2]
      title = parentDir.charAt(0).toUpperCase() + parentDir.slice(1)
    }
  }

  // Ensure title and sub are not too long for the image
  if (title.length > 50) {
    title = title.substring(0, 47) + '...'
  }
  if (sub.length > 80) {
    sub = sub.substring(0, 77) + '...'
  }

  // Clean up for URL encoding
  title = encodeURIComponent(title)
  sub = encodeURIComponent(sub)

  const params = new URLSearchParams({
    logo: logo,
    title: title,
    sub: sub,
    name: name,
    website: website,
    dark: 'false'
  })

  return `${baseUrl}?${params.toString()}`
}

export const transformHead = ({ pageData }) => {
  const ogImageUrl = generateDynamicOGImage(pageData)
  const pageTitle = pageData?.title ? `${pageData.title} | Nexios` : 'Nexios - Python Web Framework'
  const pageDescription = pageData?.description || 'Nexios is a modern, fast, and secure web framework for Python. It is designed to be easy to use and understand, while also being powerful and flexible.'

  return [
    // Open Graph tags
    ['meta', { property: 'og:title', content: pageTitle }],
    ['meta', { property: 'og:description', content: pageDescription }],
    ['meta', { property: 'og:image', content: ogImageUrl }],
    ['meta', { property: 'og:image:width', content: '1200' }],
    ['meta', { property: 'og:image:height', content: '630' }],
    ['meta', { property: 'og:image:alt', content: `${pageData?.title || 'Nexios'} - Python Web Framework` }],

    // Twitter Card tags
    ['meta', { name: 'twitter:card', content: 'summary_large_image' }],
    ['meta', { name: 'twitter:description', content: pageDescription }],
    ['meta', { name: 'twitter:image', content: ogImageUrl }],
    ['meta', { name: 'twitter:image:alt', content: `${pageData?.title || 'Nexios'} - Python Web Framework` }],
    ['meta', { name: 'msvalidate.01', content: 'FB0815BA0CFEC5A40B567076CD30A364' }]
  ]
}
