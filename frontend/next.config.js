/** @type {import('next').NextConfig} */
const nextConfig = {
  // Only enable static export for production builds (not dev mode)
  // This allows server-side features like redirects and middleware to work in dev
  ...(process.env.NODE_ENV === 'production' && {
    output: 'export',
  }),
  
  // Disable image optimization (not supported in static export)
  images: {
    unoptimized: true,
  },
  
  // Note: rewrites() are not supported with static export (output: 'export')
  // API requests should use absolute URLs configured via environment variables
  // For development, use NEXT_PUBLIC_API_URL=http://localhost:8000
};

module.exports = nextConfig;
