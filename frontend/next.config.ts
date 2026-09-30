import type { NextConfig } from 'next'

const isStaticExport = process.env.NEXT_OUTPUT === 'export'

const nextConfig: NextConfig = {
  output: isStaticExport ? 'export' : 'standalone',
  images: { unoptimized: true },
  allowedDevOrigins: ['127.0.0.1'],
  ...(isStaticExport ? {} : {
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: `${process.env.SUPPLYCHAIN_API_ORIGIN ?? 'http://127.0.0.1:8000'}/api/:path*`,
        },
      ]
    },
  }),
}

export default nextConfig
