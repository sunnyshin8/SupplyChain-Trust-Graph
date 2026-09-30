import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'SupplyChain Trust Graph',
  description: 'Governed supply-chain disruption intelligence and human-approved mitigation.',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
